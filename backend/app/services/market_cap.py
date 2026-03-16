import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Cache: ticker -> (market_cap, timestamp)
_cache: dict[str, tuple[Optional[float], datetime]] = {}
_pending: dict[str, asyncio.Future] = {}
_lock = asyncio.Lock()

TTL_HOURS = 24


async def get_market_cap(ticker: str, ttl_seconds: int = 86400) -> Optional[float]:
    """Fetch market cap for a ticker with TTL cache and dedup."""
    if not ticker or ticker.strip() == "":
        return None

    ticker = ticker.upper().strip()

    async with _lock:
        # Check cache
        if ticker in _cache:
            cap, ts = _cache[ticker]
            if datetime.utcnow() - ts < timedelta(seconds=ttl_seconds):
                return cap

        # Check if already fetching
        if ticker in _pending:
            fut = _pending[ticker]
        else:
            fut = asyncio.get_event_loop().create_future()
            _pending[ticker] = fut
            asyncio.create_task(_fetch_market_cap(ticker, fut, ttl_seconds))

    return await asyncio.shield(fut)


async def _fetch_market_cap(ticker: str, fut: asyncio.Future, ttl_seconds: int):
    try:
        cap = await asyncio.to_thread(_yfinance_fetch, ticker)
        _cache[ticker] = (cap, datetime.utcnow())
        if not fut.done():
            fut.set_result(cap)
    except Exception as e:
        logger.warning(f"Market cap fetch failed for {ticker}: {e}")
        _cache[ticker] = (None, datetime.utcnow())
        if not fut.done():
            fut.set_result(None)
    finally:
        _pending.pop(ticker, None)


def _yfinance_fetch(ticker: str) -> Optional[float]:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        cap = getattr(info, "market_cap", None)
        return float(cap) if cap else None
    except Exception as e:
        logger.warning(f"yfinance error for {ticker}: {e}")
        return None


async def bulk_prefetch(tickers: list[str], ttl_seconds: int = 86400):
    """Pre-warm cache for all tickers concurrently."""
    unique = list({t.upper().strip() for t in tickers if t and t.strip()})
    await asyncio.gather(*[get_market_cap(t, ttl_seconds) for t in unique], return_exceptions=True)
