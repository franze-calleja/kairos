import asyncio
from urllib.parse import quote

import feedparser
import httpx

from kairos.adapters.base import disabled, error, news_id, ok, strip_html
from kairos.adapters.google_news import _published
from kairos.config import Settings
from kairos.models import AdapterResult, NewsItem

SUBREDDITS = ("stocks", "investing", "wallstreetbets")
PAUSE_SECONDS = 2.0


async def mentions(
    client: httpx.AsyncClient, settings: Settings, ticker: str, days: int
) -> AdapterResult[NewsItem]:
    if not settings.reddit_enabled:
        return AdapterResult[NewsItem](items=[], status=disabled("reddit"))
    seen: dict[str, NewsItem] = {}
    try:
        for i, sub in enumerate(SUBREDDITS):
            if i:
                await asyncio.sleep(PAUSE_SECONDS)
            url = (
                f"https://www.reddit.com/r/{sub}/search.rss?q={quote(ticker)}"
                "&restrict_sr=1&sort=new&t=week"
            )
            r = await client.get(url)
            r.raise_for_status()
            for e in feedparser.parse(r.text).entries:
                if e.get("link") and e.link not in seen:
                    seen[e.link] = NewsItem(
                        id=news_id(e.link),
                        source="reddit",
                        title=strip_html(e.get("title", "")),
                        summary=strip_html(e.get("summary", ""))[:400],
                        url=e.link,
                        published_at=_published(e),
                        related_ticker=ticker,
                    )
    except (httpx.HTTPError, ValueError, AttributeError) as e:
        return AdapterResult[NewsItem](items=list(seen.values()), status=error("reddit", str(e)))
    return AdapterResult[NewsItem](items=list(seen.values()), status=ok("reddit"))
