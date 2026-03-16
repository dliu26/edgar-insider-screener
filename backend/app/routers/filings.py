from fastapi import APIRouter, Request, HTTPException, Query
from typing import Optional
from ..models.schemas import FilingsResponse, FilingDetailResponse, FilingRecord

router = APIRouter(prefix="/api/filings", tags=["filings"])


def _apply_filters(
    filings: list[FilingRecord],
    min_value: Optional[float],
    title: Optional[str],
    signal: Optional[str],
    sort_by: str,
    sort_dir: str,
) -> list[FilingRecord]:
    result = filings

    if min_value is not None:
        result = [f for f in result if f.totalValue >= min_value]

    if title:
        title_lower = title.lower()
        result = [f for f in result if title_lower in f.title.lower()]

    if signal:
        result = [f for f in result if signal in f.signals]

    # Sort
    reverse = sort_dir.lower() == "desc"
    valid_sort_fields = {"totalValue", "transactionDate", "shares", "marketCap"}
    if sort_by in valid_sort_fields:
        result = sorted(
            result,
            key=lambda x: (getattr(x, sort_by) or 0),
            reverse=reverse,
        )

    return result


@router.get("", response_model=FilingsResponse)
async def get_filings(
    request: Request,
    min_value: Optional[float] = Query(None),
    title: Optional[str] = Query(None),
    signal: Optional[str] = Query(None),
    sort_by: str = Query("totalValue"),
    sort_dir: str = Query("desc"),
):
    cache = request.app.state.cache
    filings = _apply_filters(
        cache.filings, min_value, title, signal, sort_by, sort_dir
    )
    return FilingsResponse(
        filings=filings,
        total=len(filings),
        lastRefreshed=cache.last_refreshed,
    )


@router.get("/{filing_id}", response_model=FilingDetailResponse)
async def get_filing(filing_id: str, request: Request):
    cache = request.app.state.cache
    # Normalize ID for comparison
    normalized = filing_id.replace("_", "-")
    filing = next(
        (f for f in cache.filings if f.id.replace("_", "-") == normalized),
        None,
    )
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    # Get insider history (other filings by same insider)
    history = [
        f for f in cache.filings
        if f.insiderCik == filing.insiderCik and f.id != filing.id
    ]

    return FilingDetailResponse(**filing.model_dump(), insiderHistory=history)
