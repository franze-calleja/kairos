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
