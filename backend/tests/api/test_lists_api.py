def test_lists_api_roundtrip(client):
    r = client.post("/api/lists/watching", json={"ticker": "$smh"})
    assert r.status_code == 201
    assert r.json()["ticker"] == "SMH"
    assert r.json()["lean"] is None and r.json()["price"] is None

    body = client.get("/api/lists").json()
    assert body["holdings"] == []
    assert [e["ticker"] for e in body["watching"]] == ["SMH"]
    assert body["watching"][0]["ai_status"] is None

    assert client.post("/api/lists/watching", json={"ticker": ""}).status_code == 422
    assert client.delete("/api/lists/watching/SMH").status_code == 204
    assert client.get("/api/lists").json()["watching"] == []


def test_unknown_list_name_rejected(client):
    assert client.post("/api/lists/other", json={"ticker": "NVDA"}).status_code == 422


def test_unknown_ticker_rejected_when_adding(client, monkeypatch):
    from kairos.adapters.base import error
    from kairos.api import routes

    async def unknown(t):
        return None, error("yfinance", "unknown ticker")

    monkeypatch.setattr(routes, "get_info", unknown)
    r = client.post("/api/lists/watching", json={"ticker": "XYZQQ"})
    assert r.status_code == 422
    assert r.json() == {"detail": "Unknown ticker: XYZQQ"}


def test_ticker_still_added_when_yahoo_is_down(client, monkeypatch):
    from kairos.adapters.base import error
    from kairos.api import routes

    async def down(t):
        return None, error("yfinance", "info: ConnectError")

    monkeypatch.setattr(routes, "get_info", down)
    assert client.post("/api/lists/watching", json={"ticker": "NVDA"}).status_code == 201


def test_track_record_normalizes_ticker(client, conn):
    conn.execute(
        "INSERT INTO readings (ticker, created_at, lean, confidence, ai_status, price_at, payload)"
        " VALUES ('BRK-B', '2026-10-01T14:00:00+00:00', 'bullish', 'low', 'ok', 100, '{}')"
    )
    conn.execute("INSERT INTO outcomes VALUES (1, 1, 101, 1.0, 0.5, '2026-10-03T00:00:00+00:00')")
    conn.commit()
    body = client.get("/api/track-record", params={"ticker": "brk.b"}).json()
    assert body["by_lean"]["bullish"]["1"]["n"] == 1
