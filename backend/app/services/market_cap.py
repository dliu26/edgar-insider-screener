"""
Market data fetching: market cap and ADTV.

Primary source: Polygon.io API
  - Market cap: /v3/reference/tickers/{ticker} → results.market_cap
  - ADTV:       /v2/aggs/ticker/{ticker}/prev  → results[0].v

Fallback for market cap (if Polygon fails or key missing):
  Yahoo Finance chart API (price) × SEC EDGAR company facts (shares outstanding)
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, NamedTuple

import httpx

logger = logging.getLogger(__name__)

_SEC_HEADERS = {"User-Agent": "Daniel Liu daniel@dartmouth.edu"}
_POLYGON_BASE = "https://api.polygon.io"


class MarketData(NamedTuple):
    market_cap: Optional[float]
    adtv: Optional[float]


# Cache: ticker -> (MarketData, timestamp)
_cache: dict[str, tuple[MarketData, datetime]] = {}
_pending: dict[str, asyncio.Future] = {}
_lock = asyncio.Lock()


def _api_key() -> str:
    from ..config import settings
    return settings.polygon_api_key


async def get_market_data(
    ticker: str,
    cik: str = "",
    ttl_seconds: int = 86400,
) -> MarketData:
    """Return (market_cap, adtv) with caching and request deduplication."""
    if not ticker or not ticker.strip():
        return MarketData(None, None)

    key = ticker.upper().strip()

    async with _lock:
        if key in _cache:
            data, ts = _cache[key]
            if datetime.utcnow() - ts < timedelta(seconds=ttl_seconds):
                return data
        if key in _pending:
            fut = _pending[key]
        else:
            loop = asyncio.get_event_loop()
            fut = loop.create_future()
            _pending[key] = fut
            asyncio.create_task(_fetch(key, cik, fut))

    return await asyncio.shield(fut)


async def _fetch(ticker: str, cik: str, fut: asyncio.Future):
    try:
        data = await asyncio.to_thread(_fetch_sync, ticker, cik)
        _cache[ticker] = (data, datetime.utcnow())
        if not fut.done():
            fut.set_result(data)
    except Exception as exc:
        logger.warning(f"[{ticker}] market data fetch failed: {exc}")
        empty = MarketData(None, None)
        _cache[ticker] = (empty, datetime.utcnow())
        if not fut.done():
            fut.set_result(empty)
    finally:
        _pending.pop(ticker, None)


def _fetch_sync(ticker: str, cik: str) -> MarketData:
    api_key = _api_key()
    cap: Optional[float] = None
    adtv: Optional[float] = None

    # ── Stage 1: Polygon.io ───────────────────────────────────────────────
    if api_key:
        cap, adtv = _polygon_fetch(ticker, api_key)
    else:
        logger.warning(f"[{ticker}] POLYGON_API_KEY not set, skipping Polygon")

    # ── Stage 2: Yahoo chart price × SEC shares outstanding ───────────────
    if cap is None:
        logger.debug(f"[{ticker}] Polygon market cap unavailable, trying SEC+Yahoo fallback")
        price, yahoo_adtv = _yahoo_chart(ticker)
        if yahoo_adtv and adtv is None:
            adtv = yahoo_adtv
        if price:
            shares = _sec_shares(cik) if cik else None
            if shares:
                cap = float(shares) * price
                logger.info(
                    f"[{ticker}] market_cap fallback: {shares:,} shares × ${price:.2f} = ${cap/1e9:.2f}B"
                )
            else:
                logger.warning(f"[{ticker}] fallback failed: no shares outstanding (cik={cik!r})")
        else:
            logger.warning(f"[{ticker}] fallback failed: could not fetch price from Yahoo")

    if cap is None:
        logger.warning(f"[{ticker}] all market cap strategies exhausted — returning None")

    return MarketData(market_cap=cap, adtv=adtv)


def _polygon_fetch(ticker: str, api_key: str) -> tuple[Optional[float], Optional[float]]:
    """Fetch market cap and previous-day volume from Polygon.io."""
    cap: Optional[float] = None
    adtv: Optional[float] = None

    with httpx.Client(timeout=15) as client:
        # Market cap from ticker reference
        try:
            r = client.get(
                f"{_POLYGON_BASE}/v3/reference/tickers/{ticker}",
                params={"apiKey": api_key},
            )
            if r.status_code == 200:
                mc = r.json().get("results", {}).get("market_cap")
                if mc:
                    cap = float(mc)
                    logger.debug(f"[{ticker}] Polygon market_cap: ${cap/1e9:.2f}B")
                else:
                    logger.debug(f"[{ticker}] Polygon ticker reference: market_cap field empty")
            else:
                logger.debug(f"[{ticker}] Polygon reference HTTP {r.status_code}: {r.text[:120]}")
        except Exception as exc:
            logger.debug(f"[{ticker}] Polygon reference error: {exc}")

        # Previous-day volume for ADTV
        try:
            r2 = client.get(
                f"{_POLYGON_BASE}/v2/aggs/ticker/{ticker}/prev",
                params={"apiKey": api_key},
            )
            if r2.status_code == 200:
                results = r2.json().get("results", [])
                if results:
                    v = results[0].get("v")
                    if v:
                        adtv = float(v)
                        logger.debug(f"[{ticker}] Polygon prev volume: {adtv:,.0f}")
            else:
                logger.debug(f"[{ticker}] Polygon prev aggs HTTP {r2.status_code}")
        except Exception as exc:
            logger.debug(f"[{ticker}] Polygon prev aggs error: {exc}")

    return cap, adtv


def _yahoo_chart(ticker: str) -> tuple[Optional[float], Optional[float]]:
    """Fetch price and 3-month ADTV from Yahoo Finance chart API (no auth needed)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=3mo"
    try:
        with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True, timeout=15) as client:
            r = client.get(url)
        if r.status_code != 200:
            logger.debug(f"[{ticker}] Yahoo chart HTTP {r.status_code}")
            return None, None
        result = r.json().get("chart", {}).get("result")
        if not result:
            return None, None
        meta    = result[0].get("meta", {})
        price   = meta.get("regularMarketPrice")
        volumes = result[0].get("indicators", {}).get("quote", [{}])[0].get("volume", [])
        vols    = [v for v in volumes if v is not None and v > 0]
        adtv    = sum(vols) / len(vols) if vols else None
        return float(price) if price else None, adtv
    except Exception as exc:
        logger.debug(f"[{ticker}] Yahoo chart error: {exc}")
        return None, None


def _sec_shares(cik: str) -> Optional[int]:
    """Fetch most-recent CommonStockSharesOutstanding from SEC EDGAR company facts."""
    cik_padded = re.sub(r"^0+", "", cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    try:
        with httpx.Client(headers=_SEC_HEADERS, follow_redirects=True, timeout=20) as client:
            r = client.get(url)
        if r.status_code != 200:
            logger.debug(f"[SEC] company facts HTTP {r.status_code} for CIK {cik_padded}")
            return None
        gaap = r.json().get("facts", {}).get("us-gaap", {})
        key = "CommonStockSharesOutstanding"
        if key not in gaap:
            return None
        entries = gaap[key].get("units", {}).get("shares", [])
        candidates = [e for e in entries if e.get("form") in ("10-K", "10-Q", "10-K/A", "10-Q/A")]
        if not candidates:
            candidates = entries
        if not candidates:
            return None
        return int(sorted(candidates, key=lambda x: x.get("end", ""))[-1]["val"])
    except Exception as exc:
        logger.debug(f"[SEC] company facts error for CIK {cik_padded}: {exc}")
        return None


async def get_market_cap(ticker: str, ttl_seconds: int = 86400) -> Optional[float]:
    data = await get_market_data(ticker, ttl_seconds=ttl_seconds)
    return data.market_cap


async def bulk_prefetch(tickers: list[str], ttl_seconds: int = 86400):
    unique = list({t.upper().strip() for t in tickers if t and t.strip()})
    await asyncio.gather(
        *[get_market_data(t, ttl_seconds=ttl_seconds) for t in unique],
        return_exceptions=True,
    )
