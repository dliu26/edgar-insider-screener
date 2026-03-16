from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from typing import Optional
from .models.schemas import FilingRecord


@dataclass
class AppCache:
    filings: list[FilingRecord] = field(default_factory=list)
    last_refreshed: Optional[datetime] = None
    is_refreshing: bool = False
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire_refresh(self) -> bool:
        """Try to acquire the refresh lock. Returns True if acquired."""
        async with self._lock:
            if self.is_refreshing:
                return False
            self.is_refreshing = True
            return True

    async def release_refresh(self):
        async with self._lock:
            self.is_refreshing = False

    def update(self, filings: list[FilingRecord]):
        self.filings = filings
        self.last_refreshed = datetime.utcnow()
