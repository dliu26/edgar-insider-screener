import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .cache import AppCache
from .services.edgar_client import EdgarClient
from .services.pipeline import run_pipeline
from .routers import filings, signals, refresh, sc13d

logging.basicConfig(level=logging.INFO)
logging.getLogger("app.services.filing_parser").setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate User-Agent
    if "example.com" in settings.edgar_user_agent and "YourCompany" in settings.edgar_user_agent:
        logger.warning("Using default EDGAR User-Agent. Set EDGAR_USER_AGENT env var.")

    cache = AppCache()
    client = EdgarClient()
    app.state.cache = cache
    app.state.edgar_client = client

    # Start initial pipeline
    acquired = await cache.acquire_refresh()
    if acquired:
        asyncio.create_task(run_pipeline(cache, client))

    yield

    await client.close()


app = FastAPI(
    title="EDGAR Insider Alpha API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(filings.router)
app.include_router(signals.router)
app.include_router(refresh.router)
app.include_router(sc13d.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
