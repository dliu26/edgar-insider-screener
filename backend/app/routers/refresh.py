from fastapi import APIRouter, Request, BackgroundTasks
from ..models.schemas import RefreshResponse
from ..services.pipeline import run_pipeline

router = APIRouter(prefix="/api", tags=["refresh"])


@router.post("/refresh", response_model=RefreshResponse)
async def trigger_refresh(request: Request, background_tasks: BackgroundTasks):
    cache = request.app.state.cache
    client = request.app.state.edgar_client

    acquired = await cache.acquire_refresh()
    if not acquired:
        return RefreshResponse(status="already_running")

    background_tasks.add_task(run_pipeline, cache, client)
    return RefreshResponse(status="started")
