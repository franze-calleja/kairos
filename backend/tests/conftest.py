import pytest
from fastapi.testclient import TestClient

from kairos.api.app import create_app
from kairos.config import Settings
from kairos.db import connect, init_db


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        db_path=str(tmp_path / "kairos.db"),
        scheduler_enabled=False,
        gemini_api_key=None,
        finnhub_api_key=None,
        sec_user_agent=None,
    )


@pytest.fixture
def conn(settings):
    c = connect(settings.db_path)
    init_db(c, settings)
    yield c
    c.close()


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture(autouse=True)
def known_tickers(monkeypatch):
    """Adding to a list checks the ticker exists via Yahoo; stub it (tests may override)."""
    from kairos.adapters.base import ok
    from kairos.api import routes

    async def known(ticker):
        return {"quoteType": "EQUITY"}, ok("yfinance")

    monkeypatch.setattr(routes, "get_info", known)
