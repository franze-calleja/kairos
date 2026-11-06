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


def test_list_entry_has_move_summary(client, src):
    from kairos.ai.schema import Claim
    from tests.helpers import series

    src.closes = {"NVDA": series(last=-9.3), "VOO": series(last=-4.4)}
    src.move_reason = Claim(text="Chip sell-off", source_ids=["x"])
    client.post("/api/lists/holdings", json={"ticker": "NVDA"})
    client.get("/api/readings/NVDA")
    (e,) = client.get("/api/lists").json()["holdings"]
    assert e["move_date"] == "2026-10-30"
    assert e["move_notable"] is True
    assert e["move_change_pct"] == pytest.approx(-9.3, abs=0.01)
    assert 0.4 < e["move_typical_pct"] < 0.6
    assert e["move_reason"] == "Chip sell-off"
    assert e["market_change_pct"] == pytest.approx(-4.4, abs=0.01)
    assert e["market_notable"] is True


def test_list_entry_from_old_payload_has_null_move_fields(client, src, settings):
    import json

    from kairos.db import connect

    client.post("/api/lists/holdings", json={"ticker": "NVDA"})
    client.get("/api/readings/NVDA")
    c = connect(settings.db_path)
    row = c.execute("SELECT id, payload FROM readings").fetchone()
    old = json.loads(row["payload"])
    old.pop("move"), old.pop("changes"), old["ai"].pop("move_reason")
    c.execute("UPDATE readings SET payload = ? WHERE id = ?", (json.dumps(old), row["id"]))
    c.commit()
    c.close()
    r = client.get("/api/lists")
    assert r.status_code == 200
    (e,) = r.json()["holdings"]
    for k in (
        "move_date",
        "move_notable",
        "move_change_pct",
        "move_typical_pct",
        "move_reason",
        "market_change_pct",
        "market_notable",
    ):
        assert e[k] is None, k
