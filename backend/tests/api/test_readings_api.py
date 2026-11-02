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
    (entry,) = client.get("/api/lists").json()["holdings"]
    assert entry["ticker"] == "NVDA"
    assert entry["lean"] == "bullish" and entry["ai_status"] == "ok"
    assert entry["name"] == "NVIDIA Corporation"
    assert entry["kind"] == "stock"
    assert entry["price"] == 100.0
    assert entry["day_change_pct"] == 0.0
    assert entry["price_label"] == "near_average"
    assert entry["next_earnings"] is None
    assert entry["hype_warning"] is False
    assert entry["updated_at"] is not None


def test_list_entry_shows_current_thesis_verdict(client, src):
    client.post("/api/lists/holdings", json={"ticker": "NVDA"})
    client.put("/api/lists/holdings/NVDA/thesis", json={"thesis": "AI demand"})
    client.get("/api/readings/NVDA")
    (entry,) = client.get("/api/lists").json()["holdings"]
    assert entry["thesis_verdict"] == "challenges"
    client.put("/api/lists/holdings/NVDA/thesis", json={"thesis": "Something new"})
    (entry,) = client.get("/api/lists").json()["holdings"]
    assert entry["thesis_verdict"] is None  # stale until the next reading
