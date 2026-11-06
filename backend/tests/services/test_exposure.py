from datetime import UTC, datetime, timedelta

import pytest

from kairos.adapters.base import error, ok
from kairos.models import Holding
from kairos.services import exposure
from kairos.services.lists import add_ticker, set_shares

NOW = datetime(2026, 11, 3, 0, 0, tzinfo=UTC)
INFO = {
    "NVDA": {
        "quoteType": "EQUITY",
        "regularMarketPrice": 200.0,
        "sector": "Technology",
        "longName": "NVIDIA Corporation",
    },
    "QQQ": {"quoteType": "ETF", "regularMarketPrice": 600.0, "longName": "Invesco QQQ Trust"},
}


class Yahoo:
    def __init__(self):
        self.holdings_calls = 0
        self.info_calls = 0
        self.holdings = {
            "QQQ": [
                Holding(symbol="NVDA", name="NVIDIA Corporation", weight=0.10),
                Holding(symbol="MSFT", name="Microsoft Corporation", weight=0.08),
            ]
        }
        self.sectors = {"QQQ": {"technology": 0.5, "communication_services": 0.5}}

    async def get_info(self, t):
        self.info_calls += 1
        return (
            (INFO[t], ok("yfinance"))
            if t in INFO
            else (None, error("yfinance", "info: ConnectError"))
        )

    async def get_top_holdings(self, t):
        self.holdings_calls += 1
        h = self.holdings.get(t, [])
        return h, ok("yfinance") if h else error("yfinance", "no holdings data")

    async def get_sector_weightings(self, t):
        s = self.sectors.get(t, {})
        return s, ok("yfinance") if s else error("yfinance", "no sector data")


@pytest.fixture
def yahoo(monkeypatch):
    y = Yahoo()
    exposure._cache.clear()
    for name in ("get_info", "get_top_holdings", "get_sector_weightings"):
        monkeypatch.setattr(exposure, name, getattr(y, name))
    return y


def hold(conn, ticker, shares):
    add_ticker(conn, "holdings", ticker)
    set_shares(conn, ticker, shares)


def by(items, key, value):
    return next(i for i in items if i[key] == value)


async def test_direct_and_look_through(conn, yahoo):
    hold(conn, "NVDA", 10)
    hold(conn, "QQQ", 5)
    r = await exposure.compute_exposure(conn, NOW)
    assert r["total_value"] == 5000
    assert by(r["positions"], "ticker", "QQQ")["weight"] == pytest.approx(0.6)
    nvda = by(r["underlying"], "symbol", "NVDA")
    assert nvda["weight"] == pytest.approx(0.46)
    assert nvda["direct"] == pytest.approx(0.40)
    assert nvda["via"] == {"QQQ": pytest.approx(0.06)}
    assert by(r["underlying"], "symbol", "MSFT")["weight"] == pytest.approx(0.048)
    assert r["rest_of_funds"] == pytest.approx(0.492)
    assert by(r["sectors"], "sector", "Technology")["weight"] == pytest.approx(0.70)
    assert by(r["sectors"], "sector", "Communication Services")["weight"] == pytest.approx(0.30)
    assert r["underlying"][0]["symbol"] == "NVDA"
    assert r["missing_prices"] == []


async def test_missing_price_excluded(conn, yahoo):
    hold(conn, "NVDA", 10)
    hold(conn, "ZZZZ", 3)
    r = await exposure.compute_exposure(conn, NOW)
    assert r["missing_prices"] == ["ZZZZ"]
    assert r["total_value"] == 2000


async def test_etf_without_holdings_all_rest(conn, yahoo):
    yahoo.holdings = {}
    yahoo.sectors = {}
    hold(conn, "QQQ", 5)
    r = await exposure.compute_exposure(conn, NOW)
    assert r["rest_of_funds"] == pytest.approx(1.0)
    assert r["underlying"] == []
    assert r["sectors"] == [{"sector": "Unknown", "weight": pytest.approx(1.0)}]


async def test_no_shares_empty(conn, yahoo):
    add_ticker(conn, "holdings", "NVDA")
    r = await exposure.compute_exposure(conn, NOW)
    assert r["total_value"] == 0
    assert r["positions"] == [] and r["underlying"] == [] and r["sectors"] == []


async def test_uses_recent_reading_price(conn, yahoo):
    hold(conn, "NVDA", 10)
    payload = '{"kind": "stock", "price": {"last_price": 210.0}, "name": "NVIDIA Corporation"}'
    conn.execute(
        "INSERT INTO readings (ticker, created_at, ai_status, price_at, payload) "
        "VALUES (?, ?, 'ok', 210, ?)",
        ("NVDA", (NOW - timedelta(hours=2)).isoformat(), payload),
    )
    conn.commit()
    yahoo.info_calls = 0
    r = await exposure.compute_exposure(conn, NOW)
    assert by(r["positions"], "ticker", "NVDA")["price"] == 210.0
    # Info is still needed for the stock's sector, but the price comes from the reading.


async def test_cache_reused_within_6h(conn, yahoo):
    hold(conn, "QQQ", 5)
    await exposure.compute_exposure(conn, NOW)
    await exposure.compute_exposure(conn, NOW + timedelta(hours=1))
    assert yahoo.holdings_calls == 1
    await exposure.compute_exposure(conn, NOW + timedelta(hours=7))
    assert yahoo.holdings_calls == 2


async def test_failed_fetch_is_not_cached(conn, yahoo):
    hold(conn, "QQQ", 5)
    good = yahoo.holdings
    yahoo.holdings = {}
    first = await exposure.compute_exposure(conn, NOW)
    assert first["rest_of_funds"] == pytest.approx(1.0)
    yahoo.holdings = good
    second = await exposure.compute_exposure(conn, NOW + timedelta(minutes=1))
    assert second["underlying"], "a transient Yahoo failure must not stick for 6 hours"


async def test_logged_trades_override_manual_shares(conn, yahoo):
    from datetime import date

    from kairos.services.trades import add_trade

    add_ticker(conn, "holdings", "NVDA")
    set_shares(conn, "NVDA", 5)
    add_trade(conn, "NVDA", "buy", date(2026, 11, 2), price=180.0, now=NOW, shares=2)
    body = await exposure.compute_exposure(conn, NOW)
    (pos,) = body["positions"]
    assert pos["shares"] == 2 and pos["value"] == 400.0
    add_trade(conn, "NVDA", "sell", date(2026, 11, 2), price=190.0, now=NOW, shares=2)
    assert (await exposure.compute_exposure(conn, NOW))["positions"] == []
