from datetime import UTC, datetime, timedelta

import pytest

from kairos.adapters.base import error, not_configured, ok
from kairos.models import AdapterResult, Holding, NewsItem
from kairos.services import discover
from kairos.services.discover import UNIVERSE_PATH, load_list, run_discover, spike_score
from kairos.services.lists import add_ticker

NOW = datetime(2026, 11, 2, 3, 0, tzinfo=UTC)


def test_spike_score():
    assert spike_score([1] * 12 + [6, 6]) == 6 / 1.5
    assert spike_score([0] * 14) == 0.0


class Fake:
    def __init__(self, spiking=(), holdings=None):
        self.spiking = set(spiking)
        self.holdings = holdings or {}

    async def company_news(self, client, settings, t, days, today=None):
        if not settings.finnhub_api_key:
            return AdapterResult[NewsItem](items=[], status=not_configured("finnhub"))
        ages = [0, 0, 0, 1, 1, 1] if t in self.spiking else [5, 9]
        items = [
            NewsItem(
                id=f"{t}{i}",
                source="finnhub",
                title="t",
                summary="",
                url=f"https://e/{t}/{i}",
                published_at=NOW - timedelta(days=a),
                related_ticker=t,
            )
            for i, a in enumerate(ages)
        ]
        return AdapterResult[NewsItem](items=items, status=ok("finnhub"))

    async def get_top_holdings(self, etf):
        h = self.holdings.get(etf, [])
        return h, ok("yfinance") if h else error("yfinance", "no holdings data")

    async def get_info(self, t):
        return {"quoteType": "ETF" if t in self.holdings else "EQUITY"}, ok("yfinance")


@pytest.fixture
def fake(monkeypatch):
    def install(f, universe=("NVDA", "AVGO"), etfs=("QQQ", "SMH")):
        for name in ("company_news", "get_top_holdings", "get_info"):
            monkeypatch.setattr(discover, name, getattr(f, name))
        monkeypatch.setattr(
            discover, "load_list", lambda path: list(universe if path == UNIVERSE_PATH else etfs)
        )
        return f

    return install


async def test_excludes_owned(settings, conn, fake):
    settings.finnhub_api_key = "k"
    fake(Fake(spiking={"NVDA", "AVGO"}))
    add_ticker(conn, "holdings", "NVDA")
    items = await run_discover(settings, conn, NOW)
    spikes = [i for i in items if i["reason"].startswith("news spike")]
    assert [i["ticker"] for i in spikes] == ["AVGO"]
    assert spikes[0]["reason"].startswith("news spike: 6 articles in 2 days")


async def test_similar_reasons(settings, conn, fake):
    qqq = [
        Holding(symbol="NVDA", name="NVIDIA", weight=0.09),
        Holding(symbol="MSFT", name="Microsoft", weight=0.08),
    ]
    smh = [Holding(symbol="NVDA", name="NVIDIA", weight=0.20)]
    fake(Fake(holdings={"QQQ": qqq, "SMH": smh}))
    add_ticker(conn, "holdings", "QQQ")
    add_ticker(conn, "holdings", "NVDA")
    items = {i["ticker"]: i for i in await run_discover(settings, conn, NOW)}
    assert items["MSFT"]["reason"] == "top holding of QQQ (8.0%)"
    assert items["SMH"]["reason"] == "holds NVDA (20.0%)"
    assert "NVDA" not in items and "QQQ" not in items


async def test_no_finnhub_similar_only(settings, conn, fake, client):
    qqq = [Holding(symbol="MSFT", name="Microsoft", weight=0.08)]
    fake(Fake(spiking={"AVGO"}, holdings={"QQQ": qqq}))
    add_ticker(conn, "holdings", "QQQ")
    items = await run_discover(settings, conn, NOW)
    assert [i["ticker"] for i in items] == ["MSFT"]
    assert discover.latest_discover(conn)["spike_scan"] == "not_configured"


def test_discover_api_empty(client):
    assert client.get("/api/discover").json() == {
        "items": [],
        "created_at": None,
        "spike_scan": None,
    }


def test_universe_file_sane():
    tickers = load_list(UNIVERSE_PATH)
    assert len(tickers) >= 500
    assert {"NVDA", "AAPL", "BRK-B"} <= set(tickers)
    assert len(tickers) == len(set(tickers))


async def test_spike_scan_reports_progress(settings, conn, fake):
    settings.finnhub_api_key = "k"
    fake(Fake(), universe=("AAA", "BBB", "CCC"))
    calls = []
    await run_discover(
        settings, conn, NOW, on_progress=lambda done, total: calls.append((done, total))
    )
    assert calls[-1] == (3, 3)
    assert calls[0][1] == 3
