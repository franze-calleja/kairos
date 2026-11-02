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
        items = [
            NewsItem(
                id=news_id(e.link),
                source="google_news",
                title=strip_html(e.get("title", "")),
                summary=strip_html(e.get("summary", "")),
                url=e.link,
                published_at=_published(e),
                related_ticker=related_ticker,
            )
            for e in feed.entries
            if e.get("link")
        ]
    except (httpx.HTTPError, ValueError, AttributeError) as e:
        return AdapterResult[NewsItem](items=[], status=error("google_news", safe_detail(e)))
    return AdapterResult[NewsItem](items=items, status=ok("google_news"))
