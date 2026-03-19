from fastapi import APIRouter, Request, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta
from ..models.schemas import FilingsResponse, FilingDetailResponse, FilingRecord

router = APIRouter(prefix="/api/filings", tags=["filings"])

TITLE_GROUPS: dict[str, list[str]] = {
    "ceo":             ["chief executive", "ceo"],
    "cfo":             ["chief financial", "cfo"],
    "coo":             ["chief operating", "coo"],
    "president":       ["president"],
    "chairman":        ["chairman"],
    "vp":              ["vice president", " vp ", "svp", "evp"],
    "general_counsel": ["general counsel", "chief legal", "clco"],
    "officer":         ["officer", "cto", "ciso", "cmo", "chief"],
    "director":        ["director"],
    "10pct_owner":     ["10% owner", "10 percent", "ten percent"],
}


def _title_matches(title: str, group: str) -> bool:
    title_lower = title.lower()
    keywords = TITLE_GROUPS.get(group, [])
    if group == "other":
        for kws in TITLE_GROUPS.values():
            if any(k in title_lower for k in kws):
                return False
        return True
    return any(k in title_lower for k in keywords)


def _apply_filters(
    filings: list[FilingRecord],
    min_value: Optional[float],
    max_market_cap: Optional[float],
    min_adtv: Optional[float],
    title: Optional[str],
    title_group: Optional[str],
    signal: Optional[str],
    insider_type: Optional[str],
    sector: Optional[str],
    ticker: Optional[str],
    days: Optional[int],
    sort_by: str,
    sort_dir: str,
) -> list[FilingRecord]:
    result = filings

    if days:
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = [f for f in result if f.transactionDate >= cutoff]

    if min_value is not None:
        result = [f for f in result if f.totalValue >= min_value]

    if max_market_cap is not None:
        result = [f for f in result if f.marketCap is None or f.marketCap <= max_market_cap]

    if min_adtv is not None:
        result = [f for f in result if f.adtv is not None and f.adtv >= min_adtv]

    if ticker:
        ticker_upper = ticker.upper().strip()
        result = [f for f in result if f.ticker.upper() == ticker_upper]

    if title:
        result = [f for f in result if title.lower() in f.title.lower()]

    if title_group and title_group != "all":
        if title_group == "other":
            result = [f for f in result if _title_matches(f.title, "other")]
        elif title_group in TITLE_GROUPS:
            result = [f for f in result if _title_matches(f.title, title_group)]

    if signal:
        result = [f for f in result if signal in f.signals]

    if insider_type and insider_type in ("corporate", "institutional"):
        result = [f for f in result if f.insiderType == insider_type]

    if sector:
        result = [f for f in result if f.sector == sector]

    reverse = sort_dir.lower() == "desc"
    valid_fields = {"totalValue", "transactionDate", "shares", "marketCap", "adtv"}
    if sort_by in valid_fields:
        result = sorted(result, key=lambda x: (getattr(x, sort_by) or 0), reverse=reverse)

    return result


@router.get("", response_model=FilingsResponse)
async def get_filings(
    request: Request,
    days: Optional[int]             = Query(None),
    min_value: Optional[float]      = Query(None),
    max_market_cap: Optional[float] = Query(None),
    min_adtv: Optional[float]       = Query(None),
    ticker: Optional[str]           = Query(None),
    title: Optional[str]            = Query(None),
    title_group: Optional[str]      = Query(None),
    signal: Optional[str]           = Query(None),
    insider_type: Optional[str]     = Query(None),
    sector: Optional[str]           = Query(None),
    sort_by: str                    = Query("totalValue"),
    sort_dir: str                   = Query("desc"),
):
    cache = request.app.state.cache
    filings = _apply_filters(
        cache.filings, min_value, max_market_cap, min_adtv,
        title, title_group, signal, insider_type, sector,
        ticker, days, sort_by, sort_dir,
    )
    return FilingsResponse(
        filings=filings,
        total=len(filings),
        lastRefreshed=cache.last_refreshed,
    )


@router.get("/{filing_id}", response_model=FilingDetailResponse)
async def get_filing(filing_id: str, request: Request):
    cache = request.app.state.cache
    normalized = filing_id.replace("_", "-")
    filing = next(
        (f for f in cache.filings if f.id.replace("_", "-") == normalized),
        None,
    )
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    history = [
        f for f in cache.filings
        if f.insiderCik == filing.insiderCik and f.id != filing.id
    ]
    return FilingDetailResponse(**filing.model_dump(), insiderHistory=history)
