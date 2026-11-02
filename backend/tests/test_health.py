from fastapi.testclient import TestClient

from kairos.api.app import create_app


def test_health():
    assert TestClient(create_app()).get("/api/health").json() == {"status": "ok"}
