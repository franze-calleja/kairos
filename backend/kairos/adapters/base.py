import asyncio
import hashlib
import time

import httpx

from kairos.models import SourceName, SourceStatus

USER_AGENT = "Kairos/0.1 (+https://github.com/franzecalleja/kairos)"


def ok(name: SourceName) -> SourceStatus:
    return SourceStatus(name=name, status="ok")


def error(name: SourceName, detail: str) -> SourceStatus:
    return SourceStatus(name=name, status="error", detail=detail[:200])


def not_configured(name: SourceName) -> SourceStatus:
    return SourceStatus(name=name, status="not_configured")


def disabled(name: SourceName) -> SourceStatus:
    return SourceStatus(name=name, status="disabled")


def news_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:10]


def make_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=15.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    )


class FinnhubLimiter:
    """Allows at most one Finnhub request per `interval` seconds (free tier: 60/min)."""

    def __init__(self, interval: float = 1.0) -> None:
        self.interval = interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self) -> None:
        async with self._lock:
            delay = self._last + self.interval - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = time.monotonic()


finnhub_limiter = FinnhubLimiter()
