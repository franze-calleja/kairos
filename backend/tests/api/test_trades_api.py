from datetime import date

import pandas as pd
import pytest

from kairos.adapters.base import ok
from kairos.services import closes


@pytest.fixture
def prices(monkeypatch):
    week = pd.Series({date(2026, 11, 5): 190.0, date(2026, 11, 6): 181.6})

    async def fake_closes(ticker, start):
        return week, ok("yfinance")

    monkeypatch.setattr(closes, "get_closes", fake_closes)


def test_close_endpoint_shape(client, prices):
    r = client.get("/api/prices/nvda/close", params={"date": "2026-11-05"})
    assert r.status_code == 200
    assert r.json() == {"date": "2026-11-05", "close": 190.0}


def test_close_endpoint_no_price_is_422(client, prices):
    r = client.get("/api/prices/NVDA/close", params={"date": "2026-11-01"})
    assert r.status_code == 422
    assert r.json() == {"detail": "No price for NVDA on 2026-11-01"}


@pytest.fixture
def market(monkeypatch, prices):
    from kairos.services import exposure

    async def info(ticker):
        return {"regularMarketPrice": 200.0, "quoteType": "EQUITY"}, ok("yfinance")

    monkeypatch.setattr(exposure, "get_info", info)


BUY = {"ticker": "nvda", "side": "buy", "date": "2026-11-05", "amount": 38.0, "price": 190.0}


def test_trade_round_trip_adds_holding_and_shows_in_portfolio(client, market):
    r = client.post("/api/trades", json=BUY)
    assert r.status_code == 201
    t = r.json()
    assert t["ticker"] == "NVDA" and t["shares"] == pytest.approx(0.2)
    assert [x["id"] for x in client.get("/api/trades").json()] == [t["id"]]
    assert [e["ticker"] for e in client.get("/api/lists").json()["holdings"]] == ["NVDA"]
    p = client.get("/api/portfolio").json()
    (pos,) = p["positions"]
    assert pos["ticker"] == "NVDA" and pos["value"] == pytest.approx(40.0)
    (h,) = p["history"]
    assert h["amount"] == pytest.approx(38.0)
    assert h["since_pct"] == pytest.approx(200 / 190 * 100 - 100)


def test_delete_trade_then_404(client, market):
    tid = client.post("/api/trades", json=BUY).json()["id"]
    assert client.delete(f"/api/trades/{tid}").status_code == 204
    assert client.delete(f"/api/trades/{tid}").status_code == 404


def test_oversell_is_422_with_message(client, market):
    client.post("/api/trades", json=BUY)
    sell = {"ticker": "NVDA", "side": "sell", "date": "2026-11-05", "shares": 5, "price": 190}
    r = client.post("/api/trades", json=sell)
    assert r.status_code == 422 and "only held" in r.json()["detail"]


def test_unknown_ticker_is_422(client, market, monkeypatch):
    from kairos.adapters.base import error
    from kairos.api import routes

    async def unknown(ticker):
        return None, error("yfinance", "unknown ticker")

    monkeypatch.setattr(routes, "get_info", unknown)
    r = client.post("/api/trades", json=BUY)
    assert r.status_code == 422 and r.json()["detail"] == "Unknown ticker: NVDA"


def test_removing_holding_keeps_trades_on_my_buys(client, market):
    client.post("/api/trades", json=BUY)
    client.delete("/api/lists/holdings/NVDA")
    p = client.get("/api/portfolio").json()
    assert [x["ticker"] for x in p["positions"]] == ["NVDA"]
    assert len(p["history"]) == 1


def test_portfolio_survives_yahoo_outage(client, market, monkeypatch):
    from kairos.adapters.base import error
    from kairos.services import exposure

    client.post("/api/trades", json=BUY)

    async def down(*args):
        return None, error("yfinance", "down")

    monkeypatch.setattr(closes, "get_closes", down)
    monkeypatch.setattr(exposure, "get_info", down)
    closes.clear_closes_cache()
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    (pos,) = r.json()["positions"]
    assert pos["value"] is None and pos["voo_pct"] is None
