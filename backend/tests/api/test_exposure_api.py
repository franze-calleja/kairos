def test_exposure_endpoint_empty(client):
    body = client.get("/api/exposure").json()
    assert body["total_value"] == 0
    assert set(body) >= {"positions", "underlying", "rest_of_funds", "sectors", "missing_prices"}
