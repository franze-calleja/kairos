from fastapi.testclient import TestClient

from kairos.api.app import create_app
from kairos.services import scheduler


def test_settings_no_secrets(settings):
    settings.gemini_api_key = "sk-secret-123"
    settings.finnhub_api_key = "fh-secret-456"
    with TestClient(create_app(settings)) as c:
        r = c.get("/api/settings")
    assert "sk-secret-123" not in r.text and "fh-secret-456" not in r.text
    body = r.json()
    assert body["gemini_configured"] is True
    assert body["finnhub_configured"] is True
    assert body["sec_configured"] is False
    assert body["budget"] == {"minute": 0, "day": 0, "rpm": 10, "rpd": 200}
    assert body["last_morning_run"] is None
    assert body["thresholds"]["micro_cap_usd"] == 300_000_000


def test_jobs_morning_accepted(client, monkeypatch):
    ran = []

    async def fake(settings, conn, now):
        ran.append(now)
        return {}

    monkeypatch.setattr(scheduler, "morning_job", fake)
    assert client.post("/api/jobs/morning").status_code == 202


def test_jobs_morning_conflict(client, monkeypatch):
    monkeypatch.setattr(scheduler, "_running", True)
    assert client.post("/api/jobs/morning").status_code == 409
