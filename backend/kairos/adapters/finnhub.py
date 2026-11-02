from datetime import UTC, date, datetime, timedelta

import httpx

from kairos.adapters.base import error, finnhub_limiter, news_id, not_configured, ok, strip_html
from kairos.config import Settings
from kairos.models import AdapterResult, NewsItem, SourceStatus

BASE = "https://finnhub.io/api/v1"


async def _get(client: httpx.AsyncClient, settings: Settings, path: str, params: dict) -> object:
    await finnhub_limiter.wait()
    r = await client.get(f"{BASE}{path}", params={**params, "token": settings.finnhub_api_key})
    r.raise_for_status()
    return r.json()


async def company_news(
    client: httpx.AsyncClient,
    settings: Settings,
    ticker: str,
    days: int,
    today: date | None = None,
) -> AdapterResult[NewsItem]:
    if not settings.finnhub_api_key:
        return AdapterResult[NewsItem](items=[], status=not_configured("finnhub"))
    today = today or datetime.now(UTC).date()
    params = {
        "symbol": ticker,
        "from": (today - timedelta(days=days)).isoformat(),
        "to": today.isoformat(),
    }
    try:
        data = await _get(client, settings, "/company-news", params)
        items = [
            NewsItem(
                id=news_id(a["url"]),
                source="finnhub",
                title=strip_html(a.get("headline", "")),
                summary=strip_html(a.get("summary", "")),
                url=a["url"],
                published_at=datetime.fromtimestamp(a["datetime"], UTC),
                related_ticker=ticker,
            )
            for a in (data or [])
            if a.get("url")
        ]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        return AdapterResult[NewsItem](
            items=[], status=error("finnhub", str(e) or type(e).__name__)
        )
    return AdapterResult[NewsItem](items=items, status=ok("finnhub"))


async def earnings_calendar(
    client: httpx.AsyncClient,
    settings: Settings,
    ticker: str,
    days_ahead: int = 90,
    today: date | None = None,
) -> tuple[date | None, SourceStatus]:
    if not settings.finnhub_api_key:
        return None, not_configured("finnhub")
    today = today or datetime.now(UTC).date()
    params = {
        "symbol": ticker,
        "from": today.isoformat(),
        "to": (today + timedelta(days=days_ahead)).isoformat(),
    }
    try:
        data = await _get(client, settings, "/calendar/earnings", params)
        dates = sorted(
            date.fromisoformat(e["date"])
            for e in (data or {}).get("earningsCalendar", [])
            if e.get("date") and e.get("symbol", ticker) == ticker
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as e:
        return None, error("finnhub", str(e) or type(e).__name__)
    upcoming = [d for d in dates if d >= today]
    return (upcoming[0] if upcoming else None), ok("finnhub")
