from datetime import UTC, date, datetime

import pandas as pd
import pytest

from kairos.adapters.base import ok
from kairos.services import closes
from kairos.services.closes import close_for, close_on, closes_since


def series(days: dict[str, float]) -> pd.Series:
    return pd.Series({date.fromisoformat(k): v for k, v in days.items()})


WEEK = series({"2026-11-04": 200.0, "2026-11-05": 190.0, "2026-11-06": 181.6})


def test_close_on_weekend_uses_last_trading_day():
    assert close_on(WEEK, date(2026, 11, 7)) == (date(2026, 11, 6), 181.6)
    assert close_on(WEEK, date(2026, 11, 5)) == (date(2026, 11, 5), 190.0)


def test_close_on_before_first_close_is_none():
    assert close_on(WEEK, date(2026, 11, 3)) is None


@pytest.fixture
def fetches(monkeypatch):
    calls = []

    async def fake_closes(ticker, start):
        calls.append((ticker, start))
        return WEEK, ok("yfinance")

    async def fake_info(ticker):
        return {"regularMarketPrice": 185.25, "quoteType": "EQUITY"}, ok("yfinance")

    monkeypatch.setattr(closes, "get_closes", fake_closes)
    monkeypatch.setattr(closes, "get_info", fake_info)
    return calls


async def test_today_during_market_hours_uses_live_price(fetches):
    during = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)  # 10:00 NY
    assert await close_for("NVDA", date(2026, 11, 6), during) == (date(2026, 11, 6), 185.25)


async def test_today_after_close_uses_that_close(fetches):
    after = datetime(2026, 11, 6, 22, 0, tzinfo=UTC)  # 17:00 NY
    assert await close_for("NVDA", date(2026, 11, 6), after) == (date(2026, 11, 6), 181.6)


async def test_closes_are_cached(fetches):
    now = datetime(2026, 11, 6, 22, 0, tzinfo=UTC)
    await closes_since("NVDA", date(2026, 11, 4), now)
    await closes_since("NVDA", date(2026, 11, 5), now)  # later start: reuse
    assert len(fetches) == 1
    await closes_since("NVDA", date(2026, 10, 1), now)  # earlier start: refetch
    assert len(fetches) == 2
