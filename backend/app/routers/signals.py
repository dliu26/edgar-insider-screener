from fastapi import APIRouter, Request
from ..models.schemas import SignalSummary

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/summary", response_model=SignalSummary)
async def get_signal_summary(request: Request):
    cache = request.app.state.cache
    filings = cache.filings

    cluster_buys = sum(1 for f in filings if "CLUSTER_BUY" in f.signals)
    first_ever = sum(1 for f in filings if "FIRST_EVER_BUY" in f.signals)
    high_conviction = sum(1 for f in filings if "HIGH_CONVICTION" in f.signals)
    total_signals = sum(1 for f in filings if f.signals)

    largest = max(filings, key=lambda f: f.totalValue, default=None) if filings else None

    return SignalSummary(
        totalSignals=total_signals,
        clusterBuys=cluster_buys,
        firstEverBuys=first_ever,
        highConviction=high_conviction,
        largestTransaction=largest,
    )
