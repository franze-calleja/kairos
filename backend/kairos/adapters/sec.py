import time
from datetime import UTC, date, datetime, timedelta

import httpx

from kairos.adapters.base import error, news_id, not_configured, ok, safe_detail
from kairos.config import Settings
from kairos.models import AdapterResult, NewsItem

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FORMS = {"8-K", "10-Q", "10-K"}
_CACHE_SECONDS = 24 * 3600
_ticker_cache: dict[str, object] = {}


async def _cik_for(client: httpx.AsyncClient, headers: dict, ticker: str) -> int | None:
    fetched = _ticker_cache.get("fetched_at")
    if not fetched or time.time() - float(fetched) > _CACHE_SECONDS:
        r = await client.get(TICKERS_URL, headers=headers)
        r.raise_for_status()
        mapping = {
            row["ticker"].upper().replace(".", "-"): int(row["cik_str"])
            for row in r.json().values()
        }
        _ticker_cache.update(mapping=mapping, fetched_at=time.time())
    return _ticker_cache["mapping"].get(ticker)  # type: ignore[union-attr]


async def recent_filings(
    client: httpx.AsyncClient,
    settings: Settings,
    ticker: str,
    days: int,
    today: date | None = None,
) -> AdapterResult[NewsItem]:
    if not settings.sec_user_agent:
        return AdapterResult[NewsItem](items=[], status=not_configured("sec"))
    today = today or datetime.now(UTC).date()
    headers = {"User-Agent": settings.sec_user_agent}
    try:
        cik = await _cik_for(client, headers, ticker)
        if cik is None:
            return AdapterResult[NewsItem](items=[], status=ok("sec"))
        r = await client.get(
            f"https://data.sec.gov/submissions/CIK{cik:010d}.json", headers=headers
        )
        r.raise_for_status()
        recent = r.json()["filings"]["recent"]
        since = today - timedelta(days=days)
        items = []
        for acc, filed, form, doc in zip(
            recent["accessionNumber"],
            recent["filingDate"],
            recent["form"],
            recent["primaryDocument"],
            strict=False,
        ):
            filed_on = date.fromisoformat(filed)
            if form not in FORMS or filed_on < since:
                continue
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{doc}"
            items.append(
                NewsItem(
                    id=news_id(url),
                    source="sec",
                    title=f"{form} filing",
                    summary=f"{form} filed with the SEC on {filed}.",
                    url=url,
                    published_at=datetime(filed_on.year, filed_on.month, filed_on.day, tzinfo=UTC),
                    related_ticker=ticker,
                )
            )
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        return AdapterResult[NewsItem](items=[], status=error("sec", safe_detail(e)))
    return AdapterResult[NewsItem](items=items, status=ok("sec"))
