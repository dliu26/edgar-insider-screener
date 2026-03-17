import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import Optional
from ..config import settings
from ..cache import AppCache
from .edgar_client import EdgarClient
from .filing_parser import parse_form4_xml, TECH_SIC_CODES
from .market_cap import bulk_prefetch, get_market_cap
from .signal_detector import apply_signals

logger = logging.getLogger(__name__)

WWW_BASE = "https://www.sec.gov"
DATA_BASE = "https://data.sec.gov"
TICKERS_URL = f"{WWW_BASE}/files/company_tickers.json"

# In-memory cache for discovered tech company CIKs
_tech_cik_cache: dict[str, str] = {}   # cik (zero-padded 10-digit str) -> ticker
_tech_cik_timestamp: Optional[datetime] = None
TECH_CIK_TTL_HOURS = 24


def _last_n_business_days(n: int) -> date:
    """Return the date n business days ago."""
    d = datetime.utcnow().date()
    count = 0
    while count < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:   # Mon–Fri
            count += 1
    return d


# ---------------------------------------------------------------------------
# Tech company discovery via company_tickers.json + submissions SIC check
# ---------------------------------------------------------------------------

async def _fetch_submissions(client: EdgarClient, cik_padded: str) -> Optional[dict]:
    """Fetch data.sec.gov/submissions/CIK{cik}.json for one company."""
    url = f"{DATA_BASE}/submissions/CIK{cik_padded}.json"
    try:
        resp = await client.get(url)
        return resp.json()
    except Exception:
        return None


async def _build_tech_cik_map(client: EdgarClient) -> dict[str, str]:
    """
    Download company_tickers.json, then check each company's submissions for
    a tech SIC code.  Returns {cik_10digit -> ticker}.

    Cold-start note: ~10 k companies at 8 rps ≈ 20 min. Result is cached for
    TECH_CIK_TTL_HOURS so subsequent pipeline runs are fast.
    """
    logger.info("Building tech-company CIK map from company_tickers.json …")
    resp = await client.get(TICKERS_URL)
    entries = list(resp.json().values())   # [{cik_str, ticker, title}, …]
    logger.info(f"company_tickers.json: {len(entries)} companies to scan")

    result: dict[str, str] = {}

    async def check(entry: dict):
        cik = str(entry["cik_str"]).zfill(10)
        ticker = entry.get("ticker", "")
        data = await _fetch_submissions(client, cik)
        if data and str(data.get("sic", "")) in TECH_SIC_CODES:
            return (cik, ticker)
        return None

    results = await asyncio.gather(*[check(e) for e in entries], return_exceptions=True)
    for r in results:
        if isinstance(r, tuple):
            result[r[0]] = r[1]

    logger.info(f"Discovered {len(result)} tech companies (SIC codes: {TECH_SIC_CODES})")
    return result


async def get_tech_ciks(client: EdgarClient) -> dict[str, str]:
    """Return cached {cik -> ticker} for tech companies, refreshed every 24 h."""
    global _tech_cik_cache, _tech_cik_timestamp
    if _tech_cik_cache and _tech_cik_timestamp:
        if datetime.utcnow() - _tech_cik_timestamp < timedelta(hours=TECH_CIK_TTL_HOURS):
            return _tech_cik_cache
    _tech_cik_cache = await _build_tech_cik_map(client)
    _tech_cik_timestamp = datetime.utcnow()
    return _tech_cik_cache


# ---------------------------------------------------------------------------
# Per-company Form 4 fetching
# ---------------------------------------------------------------------------

def _recent_form4_entries(submissions: dict, cutoff: date) -> list[tuple[str, str]]:
    """
    From a submissions JSON, return (accession_dashed, primary_document) pairs
    for Form 4 / 4-A filings on or after *cutoff*.
    """
    recent = submissions.get("filings", {}).get("recent", {})
    forms       = recent.get("form", [])
    accessions  = recent.get("accessionNumber", [])
    dates       = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])

    entries = []
    for form, acc, date_str, doc in zip(forms, accessions, dates, primary_docs):
        if form not in ("4", "4/A"):
            continue
        try:
            if datetime.strptime(date_str, "%Y-%m-%d").date() < cutoff:
                continue
        except ValueError:
            continue
        entries.append((acc, doc))
    return entries


async def _fetch_form4_xml(
    client: EdgarClient,
    cik: str,
    acc_dashed: str,
    primary_doc: str,
) -> Optional[bytes]:
    """
    Fetch Form 4 XML bytes from www.sec.gov/Archives.
    Tries the primaryDocument name first; falls back to the accession-number.xml
    convention used by many Form 4 filers.
    """
    cik_plain   = cik.lstrip("0")
    acc_nodash  = acc_dashed.replace("-", "")
    base_path   = f"{WWW_BASE}/Archives/edgar/data/{cik_plain}/{acc_nodash}"

    for filename in (primary_doc, f"{acc_dashed}.xml"):
        if not filename:
            continue
        try:
            resp = await client.get(f"{base_path}/{filename}")
            return resp.content
        except Exception:
            continue
    return None


async def _process_company(
    client: EdgarClient,
    cik: str,
    cutoff: date,
    seen: set,
) -> list:
    """
    Fetch submissions for one tech company, find recent Form 4s, parse XMLs.
    Returns a (possibly empty) list of FilingRecord objects.
    """
    submissions = await _fetch_submissions(client, cik)
    if not submissions:
        return []

    records = []
    for acc_dashed, primary_doc in _recent_form4_entries(submissions, cutoff):
        acc_nodash = acc_dashed.replace("-", "")
        if acc_nodash in seen:
            continue

        cik_plain   = cik.lstrip("0")
        filing_url  = f"{WWW_BASE}/Archives/edgar/data/{cik_plain}/{acc_nodash}/"

        xml_bytes = await _fetch_form4_xml(client, cik, acc_dashed, primary_doc)
        if not xml_bytes:
            logger.debug(f"No XML for {acc_dashed}")
            continue

        parsed = parse_form4_xml(xml_bytes, acc_dashed, filing_url)
        if parsed:
            seen.add(acc_nodash)
            records.extend(parsed)

    return records


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedup_filings(filings):
    """Keep one record per (issuerCik, insiderCik, transactionDate), preferring amendments."""
    seen: dict = {}
    for f in filings:
        key = (f.issuerCik, f.insiderCik, f.transactionDate)
        if key not in seen or "/A" in f.id:
            seen[key] = f
    return list(seen.values())


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run_pipeline(cache: AppCache, client: EdgarClient):
    """fetch → filter → parse → signal → cache."""
    logger.info("Pipeline started")
    try:
        cutoff = _last_n_business_days(30)

        # 1. Resolve tech company CIKs (cached after first run)
        tech_ciks = await get_tech_ciks(client)
        logger.info(f"Processing {len(tech_ciks)} tech companies for Form 4s since {cutoff}")

        # 2. Fetch submissions + XMLs for every tech company concurrently
        seen_accessions: set = set()
        tasks = [
            _process_company(client, cik, cutoff, seen_accessions)
            for cik in tech_ciks
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        filings_raw = []
        for r in results:
            if isinstance(r, list):
                filings_raw.extend(r)
        logger.info(f"Fetched {len(filings_raw)} raw Form 4 records")

        # 3. Keep only open-market purchases (code "P"), no 10b5-1 plans
        filings = [f for f in filings_raw if f.transactionType == "P" and not f.is10b51]
        logger.info(f"After transaction filter: {len(filings)} filings")

        # 4. Deduplicate (prefer amendments over originals)
        filings = _dedup_filings(filings)
        logger.info(f"After dedup: {len(filings)} filings")

        # 5. Market-cap filter
        tickers = [f.ticker for f in filings if f.ticker]
        await bulk_prefetch(tickers, settings.market_cap_ttl_seconds)

        filtered = []
        for f in filings:
            cap = await get_market_cap(f.ticker, settings.market_cap_ttl_seconds) if f.ticker else None
            updated = f.model_copy(update={"marketCap": cap})
            if cap is None or cap <= settings.max_market_cap_usd:
                filtered.append(updated)
        logger.info(f"After market-cap filter: {len(filtered)} filings")

        # 6. Signal detection
        with_signals = await apply_signals(filtered, client)
        logger.info(f"Pipeline complete: {len(with_signals)} filings with signals")

        # 7. Publish to cache
        cache.update(with_signals)

    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
    finally:
        await cache.release_refresh()
