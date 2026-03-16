import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from ..models.schemas import FilingRecord
from .edgar_client import EdgarClient

logger = logging.getLogger(__name__)

COMP_ESTIMATES = {
    "ceo": 500_000,
    "chief executive": 500_000,
    "cfo": 400_000,
    "chief financial": 400_000,
    "director": 150_000,
}
DEFAULT_COMP = 200_000
HIGH_CONVICTION_MULTIPLIER = 10

# Cache: insider_cik -> (has_prior_buys: bool, timestamp)
_first_ever_cache: dict[str, tuple[bool, datetime]] = {}
FIRST_EVER_TTL_DAYS = 7


def estimate_comp(title: str) -> float:
    title_lower = title.lower()
    for keyword, comp in COMP_ESTIMATES.items():
        if keyword in title_lower:
            return comp
    return DEFAULT_COMP


async def detect_first_ever_buy(
    insider_cik: str,
    current_accession: str,
    client: EdgarClient,
) -> bool:
    """Check if this insider has any prior Form 4 filings."""
    cached = _first_ever_cache.get(insider_cik)
    if cached:
        has_prior, ts = cached
        if datetime.utcnow() - ts < timedelta(days=FIRST_EVER_TTL_DAYS):
            return not has_prior

    url = f"https://data.sec.gov/submissions/CIK{insider_cik}.json"
    try:
        resp = await client.get(url)
        data = resp.json()
        forms = data.get("filings", {}).get("recent", {}).get("form", [])
        accessions = data.get("filings", {}).get("recent", {}).get("accessionNumber", [])

        has_prior = False
        for form, acc in zip(forms, accessions):
            normalized_acc = acc.replace("-", "")
            current_normalized = current_accession.replace("-", "")
            if form in ("4", "4/A") and normalized_acc != current_normalized:
                has_prior = True
                break

        _first_ever_cache[insider_cik] = (has_prior, datetime.utcnow())
        return not has_prior
    except Exception as e:
        logger.warning(f"First ever check failed for {insider_cik}: {e}")
        return False


def detect_cluster_buy(filings: list[FilingRecord], window_days: int = 30) -> set[str]:
    """Return set of issuerCiks that have cluster buys."""
    from collections import defaultdict
    cutoff = datetime.utcnow() - timedelta(days=window_days)

    by_issuer: dict[str, set[str]] = defaultdict(set)
    for f in filings:
        try:
            txn_date = datetime.strptime(f.transactionDate, "%Y-%m-%d")
        except ValueError:
            continue
        if txn_date >= cutoff:
            by_issuer[f.issuerCik].add(f.insiderCik)

    return {cik for cik, insiders in by_issuer.items() if len(insiders) >= 2}


def detect_high_conviction(filing: FilingRecord) -> bool:
    """Flag if total value > 10x estimated annual comp."""
    comp = estimate_comp(filing.title)
    return filing.totalValue > HIGH_CONVICTION_MULTIPLIER * comp


async def apply_signals(
    filings: list[FilingRecord],
    client: EdgarClient,
) -> list[FilingRecord]:
    """Detect and attach all signals to filings in-place."""
    cluster_issuers = detect_cluster_buy(filings)

    # First Ever Buy: check all insiders concurrently
    first_ever_tasks = {
        f.insiderCik: detect_first_ever_buy(f.insiderCik, f.id, client)
        for f in filings
    }
    # Deduplicate by insider CIK
    unique_insider_ciks = list(first_ever_tasks.keys())
    results = await asyncio.gather(
        *[first_ever_tasks[cik] for cik in unique_insider_ciks],
        return_exceptions=True,
    )
    first_ever_map = {
        cik: (result if isinstance(result, bool) else False)
        for cik, result in zip(unique_insider_ciks, results)
    }

    updated = []
    for f in filings:
        signals = []
        if first_ever_map.get(f.insiderCik, False):
            signals.append("FIRST_EVER_BUY")
        if f.issuerCik in cluster_issuers:
            signals.append("CLUSTER_BUY")
        if detect_high_conviction(f):
            signals.append("HIGH_CONVICTION")
        updated.append(f.model_copy(update={"signals": signals}))

    return updated
