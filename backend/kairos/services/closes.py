"""The price on a given US trading day, for logged trades and the VOO comparison."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

from kairos.adapters.prices import get_closes, get_info

CLOSES_CACHE_SECONDS = 3600
MARKET_CLOSE_NY = time(16, 15)
NY = ZoneInfo("America/New_York")

_cache: dict[str, tuple[datetime, date, pd.Series]] = {}


def clear_closes_cache() -> None:
    _cache.clear()


async def closes_since(ticker: str, start: date, now: datetime) -> pd.Series | None:
    """Closes from `start` on, reused for an hour when the cached series reaches back far enough."""
    hit = _cache.get(ticker)
    if hit:
        fetched_at, cached_start, series = hit
        fresh = 0 <= (now - fetched_at).total_seconds() < CLOSES_CACHE_SECONDS
        if fresh and cached_start <= start:
            return series
    series, _status = await get_closes(ticker, start)
    if series is None or series.empty:
        return None
    _cache[ticker] = (now, start, series)
    return series


def close_on(series: pd.Series, day: date) -> tuple[date, float] | None:
    """The last close on or before `day`."""
    earlier = series[[d <= day for d in series.index]]
    if earlier.empty:
        return None
    return earlier.index[-1], float(earlier.iloc[-1])


async def close_for(ticker: str, day: date, now: datetime) -> tuple[date, float] | None:
    ny_now = now.astimezone(NY)
    if day == ny_now.date() and ny_now.time() < MARKET_CLOSE_NY:
        info, _ = await get_info(ticker)
        price = (info or {}).get("regularMarketPrice") or (info or {}).get("previousClose")
        if price:
            return day, float(price)
    series = await closes_since(ticker, day, now)
    return close_on(series, day) if series is not None else None
