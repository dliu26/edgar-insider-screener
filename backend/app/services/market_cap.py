"""
Market data fetching: market cap and ADTV.

Fallback chain for market cap:
  1. yfinance fast_info.market_cap
  2. yfinance info['marketCap']
  3. Yahoo Finance chart API (price) × SEC EDGAR company facts (shares outstanding)

ADTV is computed from the 3-month Yahoo Finance chart volume data,
with yfinance fast_info as a secondary option.
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, NamedTuple

import httpx

logger = logging.getLogger(__name__)

_YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}
_SEC_HEADERS   = {"User-Agent": "Daniel Liu daniel@dartmouth.edu"}


class MarketData(NamedTuple):
    market_cap: Optional[float]
    adtv: Optional[float]


# Cache: ticker -> (MarketData, timestamp)
_cache: dict[str, tuple[MarketData, datetime]] = {}
_pending: dict[str, asyncio.Future] = {}
_lock = asyncio.Lock()


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
    cap: Optional[float] = None
    adtv: Optional[float] = None

    # ── Stage 1: yfinance fast_info ───────────────────────────────────────
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        fi = t.fast_info
        cap_raw  = getattr(fi, "market_cap", None)
        adtv_raw = getattr(fi, "three_month_average_volume", None)
        if cap_raw:
            cap = float(cap_raw)
            logger.debug(f"[{ticker}] market_cap from yfinance fast_info: ${cap/1e9:.2f}B")
        if adtv_raw:
            adtv = float(adtv_raw)
    except Exception as exc:
        logger.debug(f"[{ticker}] yfinance fast_info failed: {exc}")

    # ── Stage 2: yfinance info dict ───────────────────────────────────────
    if not cap:
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info
            cap_raw = info.get("marketCap") or info.get("market_cap")
            if cap_raw:
                cap = float(cap_raw)
                logger.debug(f"[{ticker}] market_cap from yfinance info: ${cap/1e9:.2f}B")
            if not adtv:
                adtv_raw = info.get("averageVolume") or info.get("averageDailyVolume10Day")
                if adtv_raw:
                    adtv = float(adtv_raw)
        except Exception as exc:
            logger.debug(f"[{ticker}] yfinance info failed: {exc}")

    # ── Stage 3: Yahoo chart API + SEC EDGAR company facts ────────────────
    # Always fetch price/ADTV from Yahoo chart (reliable even when yfinance breaks)
    price, chart_adtv = _yahoo_chart(ticker)
    if chart_adtv and not adtv:
        adtv = chart_adtv

    if not cap and price:
        shares = _sec_shares(cik) if cik else None
        if shares:
            cap = float(shares) * price
            logger.debug(
                f"[{ticker}] market_cap from SEC shares × Yahoo price: "
                f"{shares:,} × ${price:.2f} = ${cap/1e9:.2f}B"
            )
        else:
            logger.warning(f"[{ticker}] could not determine shares outstanding (cik={cik!r})")

    if cap is None:
        logger.warning(f"[{ticker}] all market cap strategies failed")

    return MarketData(market_cap=cap, adtv=adtv)


def _yahoo_chart(ticker: str) -> tuple[Optional[float], Optional[float]]:
    """Fetch price and 3-month ADTV from Yahoo Finance chart API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=3mo"
    try:
        with httpx.Client(headers=_YAHOO_HEADERS, follow_redirects=True, timeout=15) as client:
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
        logger.debug(f"[{ticker}] Yahoo chart: price=${price}, ADTV={adtv:,.0f}" if adtv else
                     f"[{ticker}] Yahoo chart: price=${price}, no volume data")
        return float(price) if price else None, adtv
    except Exception as exc:
        logger.debug(f"[{ticker}] Yahoo chart failed: {exc}")
        return None, None


def _sec_shares(cik: str) -> Optional[int]:
    """Fetch most-recent CommonStockSharesOutstanding from SEC EDGAR company facts."""
    cik_padded = re.sub(r"^0+", "", cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    try:
        with httpx.Client(headers=_SEC_HEADERS, follow_redirects=True, timeout=20) as client:
            r = client.get(url)
        if r.status_code != 200:
            logger.debug(f"SEC company facts HTTP {r.status_code} for CIK {cik_padded}")
            return None
        gaap = r.json().get("facts", {}).get("us-gaap", {})
        key = "CommonStockSharesOutstanding"
        if key not in gaap:
            return None
        entries = gaap[key].get("units", {}).get("shares", [])
        candidates = [
            e for e in entries
            if e.get("form") in ("10-K", "10-Q", "10-K/A", "10-Q/A")
        ]
        if not candidates:
            candidates = entries
        if not candidates:
            return None
        return int(sorted(candidates, key=lambda x: x.get("end", ""))[-1]["val"])
    except Exception as exc:
        logger.debug(f"SEC company facts failed for CIK {cik_padded}: {exc}")
        return None


async def get_market_cap(ticker: str, ttl_seconds: int = 86400) -> Optional[float]:
    """Convenience wrapper — returns just the market cap."""
    data = await get_market_data(ticker, ttl_seconds=ttl_seconds)
    return data.market_cap


async def bulk_prefetch(tickers: list[str], ttl_seconds: int = 86400):
    """Pre-warm cache for all tickers concurrently."""
    unique = list({t.upper().strip() for t in tickers if t and t.strip()})
    await asyncio.gather(
        *[get_market_data(t, ttl_seconds=ttl_seconds) for t in unique],
        return_exceptions=True,
    )
