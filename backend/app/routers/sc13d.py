from fastapi import APIRouter, Request
from ..models.schemas import Sc13dResponse

router = APIRouter(prefix="/api/sc13d", tags=["sc13d"])


@router.get("", response_model=Sc13dResponse)
async def get_sc13d(request: Request):
    cache = request.app.state.cache
    filings = getattr(cache, "sc13d_filings", [])
    return Sc13dResponse(
        filings=filings,
        total=len(filings),
        lastRefreshed=cache.last_refreshed,
    )
