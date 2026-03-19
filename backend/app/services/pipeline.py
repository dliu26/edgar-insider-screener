import asyncio
import logging
import re
from datetime import datetime, timedelta, date
from typing import Optional

from lxml import etree

from ..config import settings
from ..cache import AppCache
from ..models.schemas import Sc13dRecord
from .edgar_client import EdgarClient
from .filing_parser import parse_form4_xml
from .market_cap import bulk_prefetch, get_market_data
from .signal_detector import apply_signals

logger = logging.getLogger(__name__)

WWW_BASE    = "https://www.sec.gov"
TICKERS_URL = f"{WWW_BASE}/files/company_tickers.json"
ATOM_NS     = "http://www.w3.org/2005/Atom"
_E          = f"{{{ATOM_NS}}}"          # shorthand for namespaced tag lookup

# In-memory cache for watchlist CIKs
_tech_cik_cache:     dict[str, str]    = {}
_tech_cik_timestamp: Optional[datetime] = None
TECH_CIK_TTL_HOURS = 24

# Finds XML document hrefs in EDGAR filing index / Atom summary HTML.
# Matches both absolute (/Archives/…) and bare relative filenames (form4.xml).
_ABS_XML_RE = re.compile(
    r'href=["\']?(/Archives/edgar/data/[^"\'\s>]+\.xml)["\']?',
    re.IGNORECASE,
)
_REL_XML_RE = re.compile(
    r'href=["\']?([^/"\'>\s]+\.xml)["\']?',
    re.IGNORECASE,
)
# Accession number: XXXXXXXXXX-YY-NNNNNN
_ACC_RE = re.compile(r'(\d{10}-\d{2}-\d{6})')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _last_n_business_days(n: int) -> date:
    d = datetime.utcnow().date()
    count = 0
    while count < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    return d


def _is_html(content: bytes) -> bool:
    sniff = content.lstrip()[:15].lower()
    return sniff.startswith(b"<!doctype") or sniff.startswith(b"<html")


# ---------------------------------------------------------------------------
# Curated watchlist (~250 small / mid-cap tech tickers)
# ---------------------------------------------------------------------------

WATCHLIST_TICKERS: frozenset[str] = frozenset({
    # ── user-provided seed ────────────────────────────────────────────────
    "ALKT", "ASAN", "BILL", "BRZE", "CFLT", "DDOG", "DOCN",
    "GTLB", "JAMF", "KRTX", "MGNI", "MQ",  "PCTY", "PUBM", "SEMR",
    "SMAR", "SPSC", "TASK", "VERX", "ZI",
    # ── SaaS / cloud software ─────────────────────────────────────────────
    "AMPL", "APPF", "APPN", "APPS", "BAND", "BIGC", "BLKB", "BL",
    "BOX",  "CDAY", "CLBT", "CWAN", "DCBO", "DBX",  "DOMO", "DOCU",
    "DV",   "EGHT", "ENFN", "ESTC", "EVER", "EVBG", "FIVN", "FOUR",
    "FRSH", "FROG", "FSLY", "GDYN", "GLBE", "GWRE", "HCAT", "HLIT",
    "HUBS", "INFA", "INST", "INTA", "LPSN", "LSPD", "MAPS", "MNDY",
    "MNTV", "NABL", "NCNO", "NTNX", "OMCL", "PAR",  "PCOR", "PEGA",
    "PHR",  "PRFT", "PRGS", "PYCR", "QTWO", "RAMP", "RNG",  "RMNI",
    "SNCR", "SPNS", "SPT",  "SQSP", "SUMO", "TOST", "TRMR", "TTGT",
    "TWLO", "TWOU", "UPLD", "WEAV", "WIX",  "XMTR", "YEXT", "ZETA",
    "ZUO",
    # ── cybersecurity ─────────────────────────────────────────────────────
    "AXON", "CGNT", "CRWD", "CYBR", "OKTA", "OSPN", "QLYS", "RBRK",
    "RDWR", "RPD",  "S",    "SCWX", "TENB", "VRNS",
    # ── fintech / payments ────────────────────────────────────────────────
    "AFRM", "ALIT", "AVDX", "BLND", "CDLX", "COIN", "DAVE", "DKNG",
    "ENVA", "EVTC", "EXFY", "FLYW", "GDRX", "HIMS", "HOOD", "LMND",
    "NVEI", "OPEN", "PAYO", "PAYC", "PSFE", "RPAY", "RSKD", "SOFI",
    "UPST", "WEX",
    # ── data / analytics / AI ─────────────────────────────────────────────
    "AI",   "ALTR", "BBAI", "DOCS", "GENI", "IONQ", "PLTR", "SOUN",
    "VERI", "VNET",
    # ── infrastructure / hardware ─────────────────────────────────────────
    "ACMR", "CEVA", "COHU", "FFIV", "FORM", "NTAP", "PSTG", "SMCI",
    "SSYS", "VIAV",
    # ── IT services / consulting ──────────────────────────────────────────
    "CACI", "CNXC", "CVLT", "DAVA", "DFIN", "EPAM", "EXLS", "EXPI",
    "FORR", "HCKT", "IBEX", "ITRI", "KFRC", "SAIC", "TTEC",
    # ── vertical SaaS / other tech ────────────────────────────────────────
    "AGYS", "ALLT", "ALRM", "ANGI", "API",  "AVNW", "BFLY", "CARS",
    "CCSI", "CHGG", "COMP", "COUR", "CRNC", "CRTO", "DUOL", "EVRI",
    "FARO", "INOD", "MITK", "MTCH", "NRDS", "RDDT", "SDGR", "SNAP",
    "UDMY", "UPWK", "YELP",
})

# Static sector mapping derived from watchlist groupings
TICKER_SECTOR: dict[str, str] = {
    **{t: "Software/SaaS" for t in [
        "ALKT","ASAN","BILL","BRZE","CFLT","DDOG","DOCN","GTLB","JAMF","KRTX",
        "MGNI","MQ","PCTY","PUBM","SEMR","SMAR","SPSC","TASK","VERX","ZI",
        "AMPL","APPF","APPN","APPS","BAND","BIGC","BLKB","BL","BOX","CDAY",
        "CLBT","CWAN","DCBO","DBX","DOMO","DOCU","DV","EGHT","ENFN","ESTC",
        "EVER","EVBG","FIVN","FOUR","FRSH","FROG","FSLY","GDYN","GLBE","GWRE",
        "HCAT","HLIT","HUBS","INFA","INST","INTA","LPSN","LSPD","MAPS","MNDY",
        "MNTV","NABL","NCNO","NTNX","OMCL","PAR","PCOR","PEGA","PHR","PRFT",
        "PRGS","PYCR","QTWO","RAMP","RNG","RMNI","SNCR","SPNS","SPT","SQSP",
        "SUMO","TOST","TRMR","TTGT","TWLO","TWOU","UPLD","WEAV","WIX","XMTR",
        "YEXT","ZETA","ZUO",
    ]},
    **{t: "Cybersecurity" for t in [
        "AXON","CGNT","CRWD","CYBR","OKTA","OSPN","QLYS","RBRK","RDWR","RPD",
        "S","SCWX","TENB","VRNS",
    ]},
    **{t: "Fintech/Payments" for t in [
        "AFRM","ALIT","AVDX","BLND","CDLX","COIN","DAVE","DKNG","ENVA","EVTC",
        "EXFY","FLYW","GDRX","HIMS","HOOD","LMND","NVEI","OPEN","PAYO","PAYC",
        "PSFE","RPAY","RSKD","SOFI","UPST","WEX",
    ]},
    **{t: "Data/AI/Analytics" for t in [
        "AI","ALTR","BBAI","DOCS","GENI","IONQ","PLTR","SOUN","VERI","VNET",
    ]},
    **{t: "Infrastructure/Hardware" for t in [
        "ACMR","CEVA","COHU","FFIV","FORM","NTAP","PSTG","SMCI","SSYS","VIAV",
    ]},
    **{t: "IT Services" for t in [
        "CACI","CNXC","CVLT","DAVA","DFIN","EPAM","EXLS","EXPI","FORR","HCKT",
        "IBEX","ITRI","KFRC","SAIC","TTEC",
    ]},
    **{t: "Vertical SaaS" for t in [
        "AGYS","ALLT","ALRM","ANGI","API","AVNW","BFLY","CARS","CCSI","CHGG",
        "COMP","COUR","CRNC","CRTO","DUOL","EVRI","FARO","INOD","MITK","MTCH",
        "NRDS","RDDT","SDGR","SNAP","UDMY","UPWK","YELP",
    ]},
}


# ---------------------------------------------------------------------------
# Watchlist CIK resolution (one HTTP request + local dict lookup, cached 24 h)
# ---------------------------------------------------------------------------

async def _build_tech_cik_map(client: EdgarClient) -> dict[str, str]:
    logger.info(f"Resolving {len(WATCHLIST_TICKERS)} watchlist tickers …")
    resp = await client.get(TICKERS_URL)
    by_ticker: dict[str, str] = {
        e["ticker"].upper(): str(e["cik_str"]).zfill(10)
        for e in resp.json().values()
        if e.get("ticker")
    }
    result: dict[str, str] = {}
    for ticker in WATCHLIST_TICKERS:
        cik = by_ticker.get(ticker.upper())
        if cik:
            result[cik] = ticker
        else:
            logger.debug(f"Ticker {ticker} not found in company_tickers.json")
    logger.info(f"Resolved {len(result)}/{len(WATCHLIST_TICKERS)} tickers to CIKs")
    return result


async def get_tech_ciks(client: EdgarClient) -> dict[str, str]:
    global _tech_cik_cache, _tech_cik_timestamp
    if _tech_cik_cache and _tech_cik_timestamp:
        if datetime.utcnow() - _tech_cik_timestamp < timedelta(hours=TECH_CIK_TTL_HOURS):
            return _tech_cik_cache
    _tech_cik_cache = await _build_tech_cik_map(client)
    _tech_cik_timestamp = datetime.utcnow()
    return _tech_cik_cache


# ---------------------------------------------------------------------------
# EDGAR Atom feed parsing
# ---------------------------------------------------------------------------

def _parse_atom(atom_bytes: bytes, cutoff: date) -> list[dict]:
    """
    Parse an EDGAR Atom feed response.  Returns a list of dicts with keys:
      acc_dashed  – accession number with dashes (e.g. "0001234567-26-000001")
      index_url   – full URL to the filing index .htm page
      summary     – raw summary HTML (contains document links for company feeds)
      filing_date – date object
    """
    try:
        root = etree.fromstring(atom_bytes)
    except etree.XMLSyntaxError as exc:
        logger.warning(f"Atom feed XML parse error: {exc}")
        return []

    entries = []
    for entry in root.findall(f"{_E}entry"):
        # ── filter to Form 4 and 4/A only ─────────────────────────────
        cat_el = entry.find(f"{_E}category")
        if cat_el is not None:
            term = cat_el.get("term", "").strip()
            if term not in ("4", "4/A"):
                continue

        # ── filing date ────────────────────────────────────────────────
        updated_raw = entry.findtext(f"{_E}updated", "")
        try:
            filing_date = datetime.strptime(updated_raw[:10], "%Y-%m-%d").date()
        except ValueError:
            filing_date = datetime.utcnow().date()

        if filing_date < cutoff:
            continue

        # ── index URL from <link> ──────────────────────────────────────
        link_el   = entry.find(f"{_E}link")
        index_url = link_el.get("href", "") if link_el is not None else ""

        # ── accession number ───────────────────────────────────────────
        # Prefer <id> field; fall back to extracting from the index URL.
        id_text = entry.findtext(f"{_E}id", "")
        m = _ACC_RE.search(id_text) or _ACC_RE.search(index_url)
        if not m:
            continue
        acc_dashed = m.group(1)

        # ── summary HTML ───────────────────────────────────────────────
        summary = entry.findtext(f"{_E}summary", "")

        entries.append(dict(
            acc_dashed=acc_dashed,
            index_url=index_url,
            summary=summary,
            filing_date=filing_date,
        ))

    return entries


# ---------------------------------------------------------------------------
# XML URL resolution: summary → index page → accession-number patterns
# ---------------------------------------------------------------------------

async def _xml_url_from_index_page(client: EdgarClient, index_url: str) -> Optional[str]:
    """
    Fetch the filing index .htm page and return the URL of the raw Form 4 XML.

    EDGAR lists two XML paths for every filing:
      /Archives/edgar/data/{cik}/{acc}/xslF345X05/form4.xml  ← XSLT-rendered HTML (7 slashes)
      /Archives/edgar/data/{cik}/{acc}/form4.xml              ← raw XML we want  (6 slashes)

    We pick the match with the fewest path components (shallowest depth), which
    is always the raw document directly inside the accession directory.
    """
    try:
        resp = await client.get(index_url)
        html = resp.text
        base = index_url.rsplit("/", 1)[0]

        # Collect all absolute XML hrefs, then prefer the shallowest path.
        candidates = _ABS_XML_RE.findall(html)
        if candidates:
            best = min(candidates, key=lambda p: p.count("/"))
            return f"{WWW_BASE}{best}"

        # Fall back to relative href (e.g. "form4.xml")
        m = _REL_XML_RE.search(html)
        if m:
            return f"{base}/{m.group(1)}"
    except Exception as exc:
        logger.debug(f"index page fetch failed ({index_url}): {exc}")
    return None


async def _resolve_xml_url(
    client:    EdgarClient,
    acc_dashed: str,
    index_url:  str,
    summary:    str,
) -> Optional[str]:
    """
    Three-stage resolution for the Form 4 XML URL:

    1. Scan the Atom entry's <summary> HTML for an absolute XML href
       (company-specific feeds embed the document table here — zero extra requests).
    2. Fetch the filing index page and scan it for XML hrefs.
    3. Fall back to well-known filename patterns under the filer's CIK path
       (filer CIK = first 10 digits of the accession number).
    """
    # Stage 1 — summary HTML (free, no extra request)
    m = _ABS_XML_RE.search(summary)
    if m:
        return f"{WWW_BASE}{m.group(1)}"

    # Stage 2 — index page (one extra request per filing)
    if index_url:
        url = await _xml_url_from_index_page(client, index_url)
        if url:
            return url

    # Stage 3 — filename guessing.
    # Try under both the issuer CIK path (from the index_url) and the filer CIK
    # (first 10 digits of the accession number), since EDGAR may store files under either.
    acc_nodash = acc_dashed.replace("-", "")
    filer_cik  = acc_nodash[:10].lstrip("0") or "0"

    # Derive issuer CIK from the index URL path, if available.
    issuer_cik = None
    if index_url:
        m = re.search(r'/Archives/edgar/data/(\d+)/', index_url)
        if m:
            issuer_cik = m.group(1)

    bases = []
    if issuer_cik and issuer_cik != filer_cik:
        bases.append(f"{WWW_BASE}/Archives/edgar/data/{issuer_cik}/{acc_nodash}")
    bases.append(f"{WWW_BASE}/Archives/edgar/data/{filer_cik}/{acc_nodash}")

    for base in bases:
        for filename in (
            f"{acc_dashed}.xml",
            "primarydoc.xml",
            "form4.xml",
            "doc4.xml",
        ):
            try:
                resp = await client.get(f"{base}/{filename}")
                if not _is_html(resp.content):
                    logger.debug(f"{acc_dashed}: found XML via fallback pattern '{filename}'")
                    return f"{base}/{filename}"
            except Exception:
                continue

    logger.warning(f"{acc_dashed}: could not locate Form 4 XML")
    return None


# ---------------------------------------------------------------------------
# Per-company processing via EDGAR company Atom feed
# ---------------------------------------------------------------------------

async def _process_company(
    client: EdgarClient,
    cik:    str,
    cutoff: date,
    seen:   set,
) -> list:
    """
    Fetch the EDGAR Atom feed for one company, then for each recent Form 4
    entry: resolve the XML URL, fetch it, and parse it.
    """
    feed_url = (
        f"{WWW_BASE}/cgi-bin/browse-edgar"
        f"?action=getcompany&CIK={cik}&type=4"
        f"&dateb=&owner=include&count=40&search_text=&output=atom"
    )

    try:
        resp    = await client.get(feed_url)
        entries = _parse_atom(resp.content, cutoff)
    except Exception as exc:
        logger.debug(f"CIK {cik}: Atom feed error — {exc}")
        return []

    records = []
    for entry in entries:
        acc_dashed = entry["acc_dashed"]
        acc_nodash = acc_dashed.replace("-", "")

        if acc_nodash in seen:
            continue

        xml_url = await _resolve_xml_url(
            client,
            acc_dashed,
            entry["index_url"],
            entry["summary"],
        )
        if not xml_url:
            continue

        try:
            xml_resp  = await client.get(xml_url)
            xml_bytes = xml_resp.content
        except Exception as exc:
            logger.debug(f"{acc_dashed}: XML fetch failed — {exc}")
            continue

        if _is_html(xml_bytes):
            logger.debug(f"{acc_dashed}: XML URL returned HTML, skipping")
            continue

        filing_url = xml_url.rsplit("/", 1)[0] + "/"
        parsed     = parse_form4_xml(xml_bytes, acc_dashed, filing_url)
        if parsed:
            seen.add(acc_nodash)
            records.extend(parsed)

    return records


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedup_filings(filings: list) -> list:
    """Keep one record per (issuerCik, insiderCik, transactionDate), preferring amendments."""
    seen: dict = {}
    for f in filings:
        key = (f.issuerCik, f.insiderCik, f.transactionDate)
        if key not in seen or "/A" in f.id:
            seen[key] = f
    return list(seen.values())


# ---------------------------------------------------------------------------
# Schedule 13D pipeline
# ---------------------------------------------------------------------------

# Regex to extract a ticker-like symbol from the company name in 13D entries
_TICKER_RE = re.compile(r'\(([A-Z]{1,5})\)')


async def run_sc13d_pipeline(
    client: EdgarClient,
    cik_to_ticker: dict[str, str],
    cutoff: date,
) -> list[Sc13dRecord]:
    """
    Fetch recent SC 13D filings from the EDGAR general Atom feed,
    filter to watchlist companies, return Sc13dRecord list.
    """
    url = (
        f"{WWW_BASE}/cgi-bin/browse-edgar"
        "?action=getcurrent&type=SC+13D&dateb=&owner=include"
        "&count=100&search_text=&output=atom"
    )
    try:
        resp = await client.get(url)
        root = etree.fromstring(resp.content)
    except Exception as exc:
        logger.warning(f"SC 13D feed fetch failed: {exc}")
        return []

    # Build reverse map: issuer name fragment → ticker (for fallback matching)
    ticker_to_cik = {v: k for k, v in cik_to_ticker.items()}

    records: list[Sc13dRecord] = []
    seen: set[str] = set()

    for entry in root.findall(f"{_E}entry"):
        # Form type filter
        cat_el = entry.find(f"{_E}category")
        if cat_el is not None:
            term = cat_el.get("term", "").strip()
            if term not in ("SC 13D", "SC 13D/A"):
                continue

        updated_raw = entry.findtext(f"{_E}updated", "")
        try:
            filing_date = datetime.strptime(updated_raw[:10], "%Y-%m-%d").date()
        except ValueError:
            filing_date = datetime.utcnow().date()
        if filing_date < cutoff:
            continue

        link_el  = entry.find(f"{_E}link")
        index_url = link_el.get("href", "") if link_el is not None else ""
        id_text  = entry.findtext(f"{_E}id", "")
        title    = entry.findtext(f"{_E}title", "")
        summary  = entry.findtext(f"{_E}summary", "")

        m = _ACC_RE.search(id_text) or _ACC_RE.search(index_url)
        if not m:
            continue
        acc_dashed = m.group(1)
        if acc_dashed in seen:
            continue

        # Extract subject company CIK from index URL
        cik_m = re.search(r'/Archives/edgar/data/(\d+)/', index_url)
        subject_cik = cik_m.group(1).zfill(10) if cik_m else ""

        # Only include if subject company is in our watchlist
        ticker = cik_to_ticker.get(subject_cik, "")
        if not ticker:
            # Try to extract ticker from title like "ACME CORP (ACME) ..."
            tk_m = _TICKER_RE.search(title)
            if tk_m:
                candidate = tk_m.group(1)
                if candidate in ticker_to_cik:
                    ticker = candidate
            if not ticker:
                continue

        # Extract issuer name from title (format: "SC 13D - COMPANY NAME (TICKER)")
        issuer_name = title.split(" - ")[-1].strip() if " - " in title else title

        # Try to extract filer name from summary HTML
        filer_name = ""
        fn_m = re.search(r'Filed by[:\s]+([^<\n]+)', summary, re.I)
        if fn_m:
            filer_name = fn_m.group(1).strip()
        if not filer_name:
            # Fall back to title prefix before the dash
            parts = title.split(" - ")
            if len(parts) >= 2:
                filer_name = parts[0].strip()

        filing_url = index_url if index_url.startswith("http") else f"{WWW_BASE}{index_url}"

        seen.add(acc_dashed)
        records.append(Sc13dRecord(
            id=acc_dashed,
            issuerName=issuer_name,
            ticker=ticker,
            issuerCik=subject_cik,
            filerName=filer_name,
            percentOwned=None,
            filingDate=str(filing_date),
            filingUrl=filing_url,
        ))

    logger.info(f"SC 13D pipeline: {len(records)} filings for watchlist companies")
    return records


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run_pipeline(cache: AppCache, client: EdgarClient):
    """Atom feed → XML fetch → parse → filter → signals → cache."""
    logger.info("Pipeline started")
    try:
        cutoff    = _last_n_business_days(90)
        tech_ciks = await get_tech_ciks(client)
        logger.info(
            f"Fetching EDGAR Atom feeds for {len(tech_ciks)} companies "
            f"(filings since {cutoff})"
        )

        seen_accessions: set = set()
        results = await asyncio.gather(
            *[_process_company(client, cik, cutoff, seen_accessions) for cik in tech_ciks],
            return_exceptions=True,
        )

        filings_raw: list = []
        for r in results:
            if isinstance(r, list):
                filings_raw.extend(r)
        logger.info(f"Fetched {len(filings_raw)} raw Form 4 records")

        # Keep open-market purchases (transactionCode "P")
        filings = [f for f in filings_raw if f.transactionType == "P"]
        logger.info(f"After purchase filter: {len(filings)} filings")

        filings = _dedup_filings(filings)
        logger.info(f"After dedup: {len(filings)} filings")

        # Market data enrichment (market cap + ADTV) + sector + filter
        # bulk_prefetch just warms the cache; per-filing fetch below passes CIK too
        tickers = [f.ticker for f in filings if f.ticker]
        await bulk_prefetch(tickers, settings.market_cap_ttl_seconds)

        filtered: list = []
        for f in filings:
            if f.ticker:
                md = await get_market_data(
                    f.ticker,
                    cik=f.issuerCik,
                    ttl_seconds=settings.market_cap_ttl_seconds,
                )
                cap  = md.market_cap
                adtv = md.adtv
            else:
                cap = adtv = None
            sector = TICKER_SECTOR.get(f.ticker.upper()) if f.ticker else None
            updated = f.model_copy(update={"marketCap": cap, "adtv": adtv, "sector": sector})
            if cap is None or cap <= settings.max_market_cap_usd:
                filtered.append(updated)
        logger.info(f"After market-cap filter: {len(filtered)} filings")

        with_signals = await apply_signals(filtered, client)
        logger.info(f"Pipeline complete: {len(with_signals)} filings with signals")

        # 13D filings
        sc13d_cutoff = _last_n_business_days(180)
        sc13d = await run_sc13d_pipeline(client, tech_ciks, sc13d_cutoff)

        cache.update(with_signals, sc13d)

    except Exception as exc:
        logger.error(f"Pipeline error: {exc}", exc_info=True)
    finally:
        await cache.release_refresh()
