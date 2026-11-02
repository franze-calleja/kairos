import pytest

from tests.services.fakes import Sources


@pytest.fixture
def src(monkeypatch):
    return Sources().install(monkeypatch)


def test_unknown_ticker_404(client, src):
    r = client.get("/api/readings/XYZQQ")
    assert r.status_code == 404
    assert r.json() == {"detail": "Unknown ticker: XYZQQ"}


def test_invalid_ticker_422(client, src):
    assert client.get("/api/readings/a;b").status_code == 422


def test_reading_ok_and_lists_show_latest_lean(client, src):
    client.post("/api/lists/holdings", json={"ticker": "NVDA"})
    r = client.get("/api/readings/nvda")
    assert r.status_code == 200
    assert r.json()["ticker"] == "NVDA"
    holdings = client.get("/api/lists").json()["holdings"]
    assert holdings == [{"ticker": "NVDA", "lean": "bullish", "ai_status": "ok"}]
