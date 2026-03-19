"""
Market data fetching: market cap and ADTV via yfinance.
Results are cached in-process with a configurable TTL.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, NamedTuple

logger = logging.getLogger(__name__)


class MarketData(NamedTuple):
    market_cap: Optional[float]
    adtv: Optional[float]   # 3-month average daily volume


# Cache: ticker -> (MarketData, timestamp)
_cache: dict[str, tuple[MarketData, datetime]] = {}
_pending: dict[str, asyncio.Future] = {}
_lock = asyncio.Lock()


async def get_market_data(ticker: str, ttl_seconds: int = 86400) -> MarketData:
    """Fetch market cap + ADTV for a ticker with TTL cache and request dedup."""
    if not ticker or not ticker.strip():
        return MarketData(None, None)

    ticker = ticker.upper().strip()

    async with _lock:
        if ticker in _cache:
            data, ts = _cache[ticker]
            if datetime.utcnow() - ts < timedelta(seconds=ttl_seconds):
                return data

        if ticker in _pending:
            fut = _pending[ticker]
        else:
            loop = asyncio.get_event_loop()
            fut = loop.create_future()
            _pending[ticker] = fut
            asyncio.create_task(_fetch(ticker, fut))

    return await asyncio.shield(fut)


async def _fetch(ticker: str, fut: asyncio.Future):
    try:
        data = await asyncio.to_thread(_yfinance_fetch, ticker)
        _cache[ticker] = (data, datetime.utcnow())
        if not fut.done():
            fut.set_result(data)
    except Exception as exc:
        logger.warning(f"Market data fetch failed for {ticker}: {exc}")
        empty = MarketData(None, None)
        _cache[ticker] = (empty, datetime.utcnow())
        if not fut.done():
            fut.set_result(empty)
    finally:
        _pending.pop(ticker, None)


def _yfinance_fetch(ticker: str) -> MarketData:
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)

        # fast_info is a lightweight call
        fi = t.fast_info
        cap = getattr(fi, "market_cap", None)
        adtv = getattr(fi, "three_month_average_volume", None)

        # Fallback to full info dict if fast_info market cap is missing
        if not cap:
            try:
                info = t.info
                cap = info.get("marketCap") or info.get("market_cap")
                if not adtv:
                    adtv = info.get("averageVolume") or info.get("averageDailyVolume10Day")
            except Exception:
                pass

        return MarketData(
            market_cap=float(cap) if cap else None,
            adtv=float(adtv) if adtv else None,
        )
    except Exception as exc:
        logger.warning(f"yfinance error for {ticker}: {exc}")
        return MarketData(None, None)


async def get_market_cap(ticker: str, ttl_seconds: int = 86400) -> Optional[float]:
    """Convenience wrapper — returns just the market cap."""
    data = await get_market_data(ticker, ttl_seconds)
    return data.market_cap


async def bulk_prefetch(tickers: list[str], ttl_seconds: int = 86400):
    """Pre-warm cache for all tickers concurrently."""
    unique = list({t.upper().strip() for t in tickers if t and t.strip()})
    await asyncio.gather(
        *[get_market_data(t, ttl_seconds) for t in unique],
        return_exceptions=True,
    )
