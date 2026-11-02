def test_lists_api_roundtrip(client):
    r = client.post("/api/lists/watching", json={"ticker": "$smh"})
    assert r.status_code == 201
    assert r.json() == {"ticker": "SMH", "lean": None, "ai_status": None}

    body = client.get("/api/lists").json()
    assert body["holdings"] == []
    assert body["watching"] == [{"ticker": "SMH", "lean": None, "ai_status": None}]

    assert client.post("/api/lists/watching", json={"ticker": ""}).status_code == 422
    assert client.delete("/api/lists/watching/SMH").status_code == 204
    assert client.get("/api/lists").json()["watching"] == []


def test_unknown_list_name_rejected(client):
    assert client.post("/api/lists/other", json={"ticker": "NVDA"}).status_code == 422
