"""S&P 500 baseline (VOO) price history, cached so a refresh job fetches it once."""

from collections.abc import Awaitable, Callable
from datetime import datetime

import pandas as pd

from kairos.models import SourceStatus

MARKET_TICKER = "VOO"
MARKET_CACHE_SECONDS = 3600

Fetch = Callable[[str], Awaitable[tuple[pd.DataFrame | None, SourceStatus]]]
_cache: tuple[datetime, pd.DataFrame] | None = None


def clear_market_cache() -> None:
    global _cache
    _cache = None


async def market_history(fetch: Fetch, now: datetime) -> pd.DataFrame | None:
    """VOO history, reused for an hour; failures are not cached."""
    global _cache
    if _cache and 0 <= (now - _cache[0]).total_seconds() < MARKET_CACHE_SECONDS:
        return _cache[1]
    df, _status = await fetch(MARKET_TICKER)
    if df is None or df.empty:
        return None
    _cache = (now, df)
    return df
