import hashlib
import json
from datetime import date
from pathlib import Path

import httpx
import respx

from kairos.adapters import finnhub, google_news, reddit, sec

FIX = Path(__file__).parent.parent / "fixtures"
TODAY = date(2026, 11, 2)


def _client():
    return httpx.AsyncClient()


@respx.mock
async def test_finnhub_parses_and_ids(settings):
    settings.finnhub_api_key = "test-key"
    respx.get("https://finnhub.io/api/v1/company-news").mock(
        return_value=httpx.Response(200, json=json.loads((FIX / "finnhub_news.json").read_text()))
    )
    async with _client() as c:
        res = await finnhub.company_news(c, settings, "NVDA", 7, today=TODAY)
    assert res.status.status == "ok"
    assert len(res.items) == 2
    first = res.items[0]
    assert first.source == "finnhub"
    assert first.id == hashlib.sha1(first.url.encode()).hexdigest()[:10]
    assert first.related_ticker == "NVDA"
    assert first.outlet == "Reuters"


@respx.mock
async def test_finnhub_no_key_not_configured(settings):
    route = respx.get("https://finnhub.io/api/v1/company-news")
    async with _client() as c:
        res = await finnhub.company_news(c, settings, "NVDA", 7, today=TODAY)
    assert res.status.status == "not_configured"
    assert res.items == []
    assert not route.called


@respx.mock
async def test_finnhub_http_500_is_error_not_raise(settings):
    settings.finnhub_api_key = "test-key"
    respx.get("https://finnhub.io/api/v1/company-news").mock(return_value=httpx.Response(500))
    async with _client() as c:
        res = await finnhub.company_news(c, settings, "NVDA", 7, today=TODAY)
    assert res.status.status == "error"
    assert res.items == []


@respx.mock
async def test_finnhub_earnings_calendar(settings):
    settings.finnhub_api_key = "test-key"
    respx.get("https://finnhub.io/api/v1/calendar/earnings").mock(
        return_value=httpx.Response(
            200, json={"earningsCalendar": [{"date": "2026-11-19", "symbol": "NVDA"}]}
        )
    )
    async with _client() as c:
        when, status = await finnhub.earnings_calendar(c, settings, "NVDA", today=TODAY)
    assert when == date(2026, 11, 19)
    assert status.status == "ok"


@respx.mock
async def test_google_news_rss_parse():
    respx.get(url__startswith="https://news.google.com/rss/search").mock(
        return_value=httpx.Response(200, text=(FIX / "google_news.rss").read_text())
    )
    async with _client() as c:
        res = await google_news.search(c, '"NVDA" OR "NVIDIA" stock', "NVDA", 7)
    assert res.status.status == "ok"
    assert len(res.items) == 2
    assert res.items[0].published_at.year == 2026
    assert res.items[0].source == "google_news"
    assert "<a" not in res.items[0].summary
    assert res.items[0].outlet == "MarketWatch"  # from <source>
    assert res.items[1].outlet == "Motley Fool"  # from the " - Outlet" title suffix
    assert res.items[1].title == "Why Nvidia shares are moving today"


@respx.mock
async def test_sec_filters_forms_and_window(settings):
    settings.sec_user_agent = "Kairos test@example.com"
    sec._ticker_cache.clear()
    respx.get("https://www.sec.gov/files/company_tickers.json").mock(
        return_value=httpx.Response(200, text=(FIX / "sec_tickers.json").read_text())
    )
    respx.get("https://data.sec.gov/submissions/CIK0001045810.json").mock(
        return_value=httpx.Response(200, text=(FIX / "sec_submissions.json").read_text())
    )
    async with _client() as c:
        res = await sec.recent_filings(c, settings, "NVDA", 7, today=TODAY)
    assert res.status.status == "ok"
    assert [i.url for i in res.items] == [
        "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000101/nvda-8k.htm"
    ]
    assert res.items[0].title == "8-K filing"
    assert res.items[0].outlet == "SEC EDGAR"


@respx.mock
async def test_sec_etf_without_cik_is_ok_empty(settings):
    settings.sec_user_agent = "Kairos test@example.com"
    sec._ticker_cache.clear()
    respx.get("https://www.sec.gov/files/company_tickers.json").mock(
        return_value=httpx.Response(200, text=(FIX / "sec_tickers.json").read_text())
    )
    async with _client() as c:
        res = await sec.recent_filings(c, settings, "QQQ", 7, today=TODAY)
    assert res.status.status == "ok"
    assert res.items == []


async def test_sec_no_user_agent_not_configured(settings):
    async with _client() as c:
        res = await sec.recent_filings(c, settings, "NVDA", 7, today=TODAY)
    assert res.status.status == "not_configured"


async def test_reddit_disabled_by_default(settings):
    async with _client() as c:
        res = await reddit.mentions(c, settings, "NVDA", 7)
    assert res.status.status == "disabled"


@respx.mock
async def test_reddit_enabled_parses(settings, monkeypatch):
    settings.reddit_enabled = True
    monkeypatch.setattr(reddit, "PAUSE_SECONDS", 0)
    respx.get(url__startswith="https://www.reddit.com/r/").mock(
        return_value=httpx.Response(200, text=(FIX / "reddit.rss").read_text())
    )
    async with _client() as c:
        res = await reddit.mentions(c, settings, "NVDA", 7)
    assert res.status.status == "ok"
    assert len(res.items) == 1  # same post from 3 subs is deduped by URL
    assert res.items[0].source == "reddit"
    assert res.items[0].outlet == "r/stocks"


@respx.mock
async def test_finnhub_key_never_in_error_or_url(settings):
    settings.finnhub_api_key = "SECRETKEY123"
    news_route = respx.get("https://finnhub.io/api/v1/company-news").mock(
        return_value=httpx.Response(401, json={"error": "Invalid API key"})
    )
    respx.get("https://finnhub.io/api/v1/calendar/earnings").mock(return_value=httpx.Response(429))
    async with _client() as c:
        res = await finnhub.company_news(c, settings, "NVDA", 7, today=TODAY)
        _, earn_status = await finnhub.earnings_calendar(c, settings, "NVDA", today=TODAY)
    assert res.status.status == "error" and earn_status.status == "error"
    assert "SECRETKEY123" not in (res.status.detail or "")
    assert "SECRETKEY123" not in (earn_status.detail or "")
    assert "401" in res.status.detail
    request = news_route.calls.last.request
    assert "SECRETKEY123" not in str(request.url)
    assert request.headers["X-Finnhub-Token"] == "SECRETKEY123"
