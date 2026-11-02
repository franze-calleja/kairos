from datetime import UTC, datetime

import pytest
from google.genai import errors

from kairos.ai import gemini
from kairos.ai.budget import RequestBudget
from kairos.ai.schema import AISummary, Claim

NOW = datetime(2026, 11, 2, 3, 0, tzinfo=UTC)


def summary(**overrides):
    base = dict(
        lean="bullish",
        confidence="medium",
        not_enough_signal=False,
        substantive_news=True,
        drivers=[Claim(text="Guidance raised", source_ids=["a"])],
        bull_case=[Claim(text="Demand", source_ids=["a"])],
        bear_case=[Claim(text="Valuation", source_ids=["a"])],
    )
    base.update(overrides)
    return AISummary(**base)


class FakeResponse:
    def __init__(self, parsed):
        self.parsed = parsed


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.aio = self
        self.models = self

    async def generate_content(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)


@pytest.fixture
def budget(conn):
    return RequestBudget(conn, rpm=10, rpd=200, tz="UTC")


@pytest.fixture
def keyed(settings):
    settings.gemini_api_key = "test-key"
    return settings


def use(monkeypatch, client):
    monkeypatch.setattr(gemini, "_client_factory", lambda key: client)
    return client


async def test_no_key_not_configured_no_budget_use(settings, budget):
    assert await gemini.summarize(settings, budget, "p", {"a"}, NOW) == (None, "not_configured")
    assert budget.usage(NOW)["day"] == 0


async def test_ok(monkeypatch, keyed, budget):
    use(monkeypatch, FakeClient([summary()]))
    result, status = await gemini.summarize(keyed, budget, "p", {"a"}, NOW)
    assert status == "ok"
    assert result.lean == "bullish"
    assert budget.usage(NOW)["day"] == 1


async def test_budget_exhausted_before_call(monkeypatch, keyed, conn):
    client = use(monkeypatch, FakeClient([summary()]))
    tight = RequestBudget(conn, rpm=0, rpd=0, tz="UTC")
    assert await gemini.summarize(keyed, tight, "p", {"a"}, NOW) == (None, "budget_exhausted")
    assert client.calls == 0


async def test_429_budget_exhausted(monkeypatch, keyed, budget):
    err = errors.ClientError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
    )
    use(monkeypatch, FakeClient([err]))
    assert await gemini.summarize(keyed, budget, "p", {"a"}, NOW) == (None, "budget_exhausted")


async def test_drops_unknown_source_claims(monkeypatch, keyed, budget):
    parsed = summary(
        drivers=[
            Claim(text="ok", source_ids=["a"]),
            Claim(text="bad", source_ids=["zzz"]),
            Claim(text="none", source_ids=[]),
        ]
    )
    use(monkeypatch, FakeClient([parsed]))
    result, status = await gemini.summarize(keyed, budget, "p", {"a"}, NOW)
    assert [d.text for d in result.drivers] == ["ok"]


async def test_all_claims_invalid_sets_not_enough_signal(monkeypatch, keyed, budget):
    parsed = summary(drivers=[Claim(text="bad", source_ids=["zzz"])])
    use(monkeypatch, FakeClient([parsed]))
    result, status = await gemini.summarize(keyed, budget, "p", {"a"}, NOW)
    assert status == "ok"
    assert result.not_enough_signal is True


async def test_retry_once_then_unavailable(monkeypatch, keyed, budget):
    client = use(monkeypatch, FakeClient([RuntimeError("boom"), None]))
    assert await gemini.summarize(keyed, budget, "p", {"a"}, NOW) == (None, "unavailable")
    assert client.calls == 2
    assert budget.usage(NOW)["day"] == 2


async def test_retry_succeeds_second_time(monkeypatch, keyed, budget):
    use(monkeypatch, FakeClient([RuntimeError("boom"), summary()]))
    result, status = await gemini.summarize(keyed, budget, "p", {"a"}, NOW)
    assert status == "ok"
