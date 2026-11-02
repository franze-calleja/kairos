from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from kairos.adapters.base import ok
from kairos.services import track_record
from kairos.services.track_record import fill_outcomes, stats

READ_DAY = "2026-10-01"
READ_AT = datetime(2026, 10, 1, 14, 0, tzinfo=UTC)


def series(start_value, step, before=5, after=25):
    """Business-day closes: `before` days up to READ_DAY (inclusive) then `after` sessions."""
    idx = pd.bdate_range(end=READ_DAY, periods=before).append(
        pd.bdate_range(start=pd.Timestamp(READ_DAY) + pd.offsets.BDay(1), periods=after)
    )
    values = [start_value] * before + [start_value + step * (i + 1) for i in range(after)]
    return pd.DataFrame({"Close": values, "Volume": [1] * len(values)}, index=idx)


class Hist:
    def __init__(self, after=25):
        self.data = {
            "NVDA": series(100.0, 1.0, after=after),
            "VOO": series(500.0, 0.5, after=after),
        }

    async def __call__(self, ticker, period="1y"):
        return self.data[ticker], ok("yfinance")


@pytest.fixture
def hist(monkeypatch):
    h = Hist()
    monkeypatch.setattr(track_record, "get_history", h)
    return h


def add_reading(conn, at=READ_AT, lean="bullish", ticker="NVDA", price=100.0):
    conn.execute(
        "INSERT INTO readings (ticker, created_at, lean, confidence, ai_status, price_at, payload)"
        " VALUES (?, ?, ?, 'medium', ?, ?, '{}')",
        (ticker, at.isoformat(), lean, "ok" if lean else "not_enough_signal", price),
    )
    conn.commit()


def outcomes(conn):
    return {
        (r["reading_id"], r["horizon"]): (
            round(r["change_pct"], 4),
            round(r["baseline_change_pct"], 4),
        )
        for r in conn.execute("SELECT * FROM outcomes")
    }


async def test_fill_horizons(settings, conn, hist):
    add_reading(conn)
    written = await fill_outcomes(settings, conn, READ_AT + timedelta(days=60))
    assert written == 3
    o = outcomes(conn)
    assert o[(1, 1)][0] == 1.0
    assert o[(1, 5)] == (5.0, 0.5)
    assert o[(1, 20)][0] == 20.0


async def test_first_reading_per_day_only(settings, conn, hist):
    for h in range(3):
        add_reading(conn, at=READ_AT + timedelta(hours=h))
    await fill_outcomes(settings, conn, READ_AT + timedelta(days=60))
    assert {k[0] for k in outcomes(conn)} == {1}


async def test_not_enough_sessions_skips(settings, conn, monkeypatch):
    h = Hist(after=3)
    monkeypatch.setattr(track_record, "get_history", h)
    add_reading(conn)
    assert await fill_outcomes(settings, conn, READ_AT + timedelta(days=5)) == 1
    assert set(outcomes(conn)) == {(1, 1)}
    h.data = Hist(after=25).data
    assert await fill_outcomes(settings, conn, READ_AT + timedelta(days=60)) == 2
    assert set(outcomes(conn)) == {(1, 1), (1, 5), (1, 20)}


async def test_null_lean_excluded(settings, conn, hist):
    add_reading(conn, lean=None)
    assert await fill_outcomes(settings, conn, READ_AT + timedelta(days=60)) == 0


async def test_stats_shape_and_small_sample(settings, conn, hist):
    add_reading(conn)
    add_reading(conn, at=READ_AT - timedelta(days=1), price=99.0)
    await fill_outcomes(settings, conn, READ_AT + timedelta(days=60))
    s = stats(conn, None)
    assert s["small_sample"] is True
    h1 = s["by_lean"]["bullish"]["1"]
    assert h1["n"] == 2
    assert h1["pct_positive"] == 100.0
    assert s["by_lean"]["bearish"]["1"]["n"] == 0
    assert s["by_lean"]["bearish"]["1"]["avg_change_pct"] is None
    assert stats(conn, "AAPL")["by_lean"]["bullish"]["1"]["n"] == 0


def test_track_record_api(client):
    body = client.get("/api/track-record").json()
    assert body["small_sample"] is True
    assert set(body["by_lean"]) == {"bullish", "neutral", "bearish"}
