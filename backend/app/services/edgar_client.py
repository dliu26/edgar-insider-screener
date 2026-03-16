import httpx
import asyncio
import logging
from aiolimiter import AsyncLimiter
from ..config import settings

logger = logging.getLogger(__name__)

# 8 rps per EDGAR domain
RATE_LIMITERS = {
    "efts.sec.gov": AsyncLimiter(8, 1),
    "data.sec.gov": AsyncLimiter(8, 1),
    "www.sec.gov": AsyncLimiter(8, 1),
}

MAX_RETRIES = 3


def _get_limiter(url: str) -> AsyncLimiter:
    for domain, limiter in RATE_LIMITERS.items():
        if domain in url:
            return limiter
    return RATE_LIMITERS["www.sec.gov"]


class EdgarClient:
    def __init__(self):
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": settings.edgar_user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": "www.sec.gov",
            },
            timeout=30.0,
            follow_redirects=True,
        )

    async def get(self, url: str, **kwargs) -> httpx.Response:
        limiter = _get_limiter(url)
        for attempt in range(MAX_RETRIES):
            async with limiter:
                try:
                    # Update Host header based on URL
                    from urllib.parse import urlparse
                    host = urlparse(url).netloc
                    headers = {"Host": host}
                    resp = await self.client.get(url, headers=headers, **kwargs)
                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
                        logger.warning(f"429 from {url}, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    resp.raise_for_status()
                    return resp
                except httpx.HTTPStatusError as e:
                    if attempt == MAX_RETRIES - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)
        raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES} attempts")

    async def close(self):
        await self.client.aclose()
