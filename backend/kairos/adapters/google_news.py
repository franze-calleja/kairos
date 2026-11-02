import calendar
from datetime import UTC, datetime
from urllib.parse import quote

import feedparser
import httpx

from kairos.adapters.base import error, news_id, ok, safe_detail, strip_html
from kairos.models import AdapterResult, NewsItem


def _published(entry: dict) -> datetime:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime.fromtimestamp(calendar.timegm(parsed), UTC)
    return datetime.now(UTC)


def _title_and_outlet(entry: dict) -> tuple[str, str | None]:
    """Google News titles end with " - Outlet"; <source> also names the outlet when present."""
    title = strip_html(entry.get("title", ""))
    suffix = None
    if " - " in title:
        head, tail = title.rsplit(" - ", 1)
        if head and 0 < len(tail) <= 60:
            title, suffix = head, tail
    source = entry.get("source") or {}
    outlet = (source.get("title") if hasattr(source, "get") else None) or suffix
    return title, outlet


async def search(
    client: httpx.AsyncClient, query: str, related_ticker: str, days: int
) -> AdapterResult[NewsItem]:
    url = (
        f"https://news.google.com/rss/search?q={quote(f'{query} when:{days}d')}"
        "&hl=en-US&gl=US&ceid=US:en"
    )
    try:
        r = await client.get(url)
        r.raise_for_status()
        feed = feedparser.parse(r.text)
        items = []
        for e in feed.entries:
            if not e.get("link"):
                continue
            title, outlet = _title_and_outlet(e)
            items.append(
                NewsItem(
                    id=news_id(e.link),
                    source="google_news",
                    title=title,
                    summary=strip_html(e.get("summary", "")),
                    url=e.link,
                    published_at=_published(e),
                    related_ticker=related_ticker,
                    outlet=outlet,
                )
            )
    except (httpx.HTTPError, ValueError, AttributeError) as e:
        return AdapterResult[NewsItem](items=[], status=error("google_news", safe_detail(e)))
    return AdapterResult[NewsItem](items=items, status=ok("google_news"))
