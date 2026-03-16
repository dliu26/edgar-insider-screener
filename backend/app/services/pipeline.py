import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from ..config import settings
from ..cache import AppCache
from .edgar_client import EdgarClient
from .filing_parser import parse_form4_xml
from .market_cap import bulk_prefetch, get_market_cap
from .signal_detector import apply_signals

logger = logging.getLogger(__name__)

TECH_SIC_CODES = {"7370", "7371", "7372", "7374", "7379"}
EFTS_BASE = "https://efts.sec.gov/EDGAR/search-index"
DATA_BASE = "https://data.sec.gov"
WWW_BASE = "https://www.sec.gov"
PAGE_SIZE = 40


def _last_n_business_days(n: int) -> str:
    """Return date string n business days ago."""
    d = datetime.utcnow().date()
    count = 0
    while count < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:  # Mon-Fri
            count += 1
    return d.strftime("%Y-%m-%d")


async def _fetch_page(client: EdgarClient, params: dict) -> dict:
    url = EFTS_BASE
    resp = await client.get(url, params=params)
    return resp.json()


async def fetch_all_form4s(client: EdgarClient) -> list[dict]:
    """Fetch all Form 4 filings from the last 30 days."""
    start_date = _last_n_business_days(30)
    today = datetime.utcnow().strftime("%Y-%m-%d")

    base_params = {
        "q": '""',
        "dateRange": "custom",
        "startdt": start_date,
        "enddt": today,
        "forms": "4",
        "_source": "period_of_report,entity_name,file_num,period_of_report,biz_location,inc_states,category",
        "hits.hits.total.value": "true",
        "hits.hits._source.period_of_report": "true",
    }

    # First page
    params = {**base_params, "from": 0, "size": PAGE_SIZE}
    first = await _fetch_page(client, params)
    hits = first.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    all_hits = hits.get("hits", [])

    logger.info(f"Total Form 4 filings in range: {total}")

    # Fetch remaining pages
    remaining_pages = []
    for offset in range(PAGE_SIZE, total, PAGE_SIZE):
        remaining_pages.append({**base_params, "from": offset, "size": PAGE_SIZE})

    if remaining_pages:
        page_results = await asyncio.gather(
            *[_fetch_page(client, p) for p in remaining_pages],
            return_exceptions=True,
        )
        for result in page_results:
            if isinstance(result, dict):
                all_hits.extend(result.get("hits", {}).get("hits", []))

    return all_hits


def _extract_sic(hit: dict) -> str:
    source = hit.get("_source", {})
    # SIC code may be in category or other fields
    category = source.get("category", "")
    # Try to get SIC from the hit
    sic = source.get("period_of_report", "")
    return source.get("biz_location", "")


async def fetch_filing_xml(client: EdgarClient, hit: dict) -> Optional[tuple]:
    """Fetch Form 4 XML. Returns (accession_number, xml_bytes, filing_url) or None."""
    try:
        source = hit.get("_source", {})
        entity_id = hit.get("_id", "")

        # The _id is typically "accession_number"
        # Build filing index URL
        # EDGAR filing format: /Archives/edgar/data/{CIK}/{accession_no_dashes}/
        file_num = source.get("file_num", "")

        # Try to get accession number from _id
        accession = entity_id
        if not accession:
            return None

        # Normalize accession number
        acc_normalized = accession.replace("-", "")
        if len(acc_normalized) != 18:
            return None

        # CIK is first 10 digits of accession
        cik = acc_normalized[:10].lstrip("0")
        acc_dashed = f"{acc_normalized[:10]}-{acc_normalized[10:12]}-{acc_normalized[12:]}"

        filing_index_url = f"{WWW_BASE}/Archives/edgar/data/{cik}/{acc_normalized}/{acc_dashed}-index.htm"
        xml_url = f"{WWW_BASE}/Archives/edgar/data/{cik}/{acc_normalized}/{acc_dashed}.xml"

        # Try primary document URL
        try:
            resp = await client.get(xml_url)
            return (acc_dashed, resp.content, f"{WWW_BASE}/Archives/edgar/data/{cik}/{acc_normalized}/")
        except Exception:
            pass

        # Fallback: try fetching filing index to find XML
        try:
            idx_resp = await client.get(
                f"{DATA_BASE}/submissions/CIK{cik.zfill(10)}.json"
            )
            # Not ideal, skip for now
        except Exception:
            pass

        return None
    except Exception as e:
        logger.debug(f"Failed to fetch filing XML: {e}")
        return None


async def run_pipeline(cache: AppCache, client: EdgarClient):
    """Main pipeline: fetch -> filter -> parse -> signal -> cache."""
    logger.info("Pipeline started")
    try:
        # 1. Fetch all Form 4s
        all_hits = await fetch_all_form4s(client)
        logger.info(f"Fetched {len(all_hits)} Form 4 hits")

        # 2. Use EDGAR full-text search with SIC filter via submissions API
        # We'll fetch XMLs and filter by SIC from the parsed data
        # Actually, use data.sec.gov company search for tech companies
        # Better approach: fetch recent Form 4s for tech SIC codes directly

        filings_raw = await _fetch_tech_form4s(client)
        logger.info(f"After SIC filter: {len(filings_raw)} filings")

        # 3. Filter: only "P" transactions, not 10b5-1
        filings = [f for f in filings_raw if not f.is10b51 and f.transactionType == "P"]
        logger.info(f"After transaction filter: {len(filings)} filings")

        # 4. Bulk fetch market caps
        tickers = [f.ticker for f in filings if f.ticker]
        await bulk_prefetch(tickers, settings.market_cap_ttl_seconds)

        # Attach market caps and filter
        filtered = []
        for f in filings:
            cap = await get_market_cap(f.ticker, settings.market_cap_ttl_seconds) if f.ticker else None
            updated = f.model_copy(update={"marketCap": cap})
            if cap is None or cap <= settings.max_market_cap_usd:
                filtered.append(updated)

        logger.info(f"After market cap filter: {len(filtered)} filings")

        # 5. Detect signals
        with_signals = await apply_signals(filtered, client)
        logger.info(f"Pipeline complete: {len(with_signals)} filings with signals")

        # 6. Update cache
        cache.update(with_signals)

    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
    finally:
        await cache.release_refresh()


async def _fetch_tech_form4s(client: EdgarClient):
    """Fetch Form 4 filings for tech SIC codes using EDGAR company search."""
    from .filing_parser import parse_form4_xml, TECH_SIC_CODES
    import asyncio

    all_filings = []
    seen_accessions: set[str] = set()

    for sic in TECH_SIC_CODES:
        try:
            # Search for companies with this SIC code that filed Form 4 recently
            url = f"{DATA_BASE}/submissions/index.json"
            # Use EDGAR full-text search
            start_date = _last_n_business_days(30)
            today = datetime.utcnow().strftime("%Y-%m-%d")

            search_url = "https://efts.sec.gov/EDGAR/search-index"
            params = {
                "q": f'"{sic}"',
                "dateRange": "custom",
                "startdt": start_date,
                "enddt": today,
                "forms": "4",
                "from": 0,
                "size": 40,
            }
            try:
                resp = await client.get(search_url, params=params)
                data = resp.json()
            except Exception:
                continue

            hits = data.get("hits", {}).get("hits", [])

            # Process hits in batches to stay under rate limit
            batch_size = 10
            for i in range(0, len(hits), batch_size):
                batch = hits[i:i + batch_size]
                results = await asyncio.gather(
                    *[_process_hit(client, hit, seen_accessions, sic) for hit in batch],
                    return_exceptions=True,
                )
                for result in results:
                    if isinstance(result, list):
                        all_filings.extend(result)

        except Exception as e:
            logger.warning(f"SIC {sic} fetch error: {e}")

    # Deduplicate amended filings: prefer amendment
    return _dedup_filings(all_filings)


async def _process_hit(client: EdgarClient, hit: dict, seen: set, sic: str):
    """Process a single search hit into filing records."""
    from .filing_parser import parse_form4_xml

    try:
        entity_id = hit.get("_id", "")
        if not entity_id:
            return []

        acc_normalized = entity_id.replace("-", "")
        if len(acc_normalized) != 18:
            return []

        if acc_normalized in seen:
            return []

        cik = acc_normalized[:10].lstrip("0")
        acc_dashed = f"{acc_normalized[:10]}-{acc_normalized[10:12]}-{acc_normalized[12:]}"

        # Try primary form4 XML URL pattern
        xml_url = f"{WWW_BASE}/Archives/edgar/data/{cik}/{acc_normalized}/{acc_dashed}.xml"
        filing_url = f"{WWW_BASE}/Archives/edgar/data/{cik}/{acc_normalized}/"

        try:
            resp = await client.get(xml_url)
            xml_bytes = resp.content
        except Exception:
            # Try alternative: fetch filing index
            try:
                idx_url = f"{DATA_BASE}/submissions/CIK{cik.zfill(10)}.json"
                # Skip for now, too many requests
                return []
            except Exception:
                return []

        records = parse_form4_xml(xml_bytes, acc_dashed, filing_url)
        if records:
            seen.add(acc_normalized)
        return records

    except Exception as e:
        logger.debug(f"Hit processing error: {e}")
        return []


def _dedup_filings(filings):
    """Deduplicate by issuer CIK + insider CIK + transaction date, preferring amendments."""
    seen = {}
    for f in filings:
        key = (f.issuerCik, f.insiderCik, f.transactionDate)
        if key not in seen:
            seen[key] = f
        else:
            # Prefer amendment (4/A) over original
            if "/A" in f.id:
                seen[key] = f
    return list(seen.values())
