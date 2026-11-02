from datetime import UTC, datetime, timedelta

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
        self.models_used = getattr(self, "models_used", []) + [kwargs["model"]]
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)


class Clock:
    def __init__(self):
        self.now = NOW
        self.slept = []

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.slept.append(seconds)
        self.now = self.now + timedelta(seconds=seconds)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(gemini, "_clock", c)
    monkeypatch.setattr(gemini, "_sleep", c.sleep)
    return c


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


async def test_gives_up_after_three_attempts(monkeypatch, keyed, budget, clock):
    client = use(monkeypatch, FakeClient([RuntimeError("boom"), None, RuntimeError("boom")]))
    assert await gemini.summarize(keyed, budget, "p", {"a"}, NOW) == (None, "unavailable")
    assert client.calls == 3
    assert budget.usage(clock.now)["day"] == 3


async def test_retry_succeeds_second_time(monkeypatch, keyed, budget):
    use(monkeypatch, FakeClient([RuntimeError("boom"), summary()]))
    result, status = await gemini.summarize(keyed, budget, "p", {"a"}, NOW)
    assert status == "ok"


def rate_limited():
    return errors.ClientError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
    )


async def test_429_twice_budget_exhausted(monkeypatch, keyed, budget):
    use(monkeypatch, FakeClient([rate_limited(), rate_limited()]))
    assert await gemini.summarize(keyed, budget, "p", {"a"}, NOW) == (None, "budget_exhausted")


async def test_429_backs_off_then_retries(monkeypatch, keyed, budget, clock):
    use(monkeypatch, FakeClient([rate_limited(), summary()]))
    result, status = await gemini.summarize(keyed, budget, "p", {"a"}, NOW)
    assert status == "ok"
    assert clock.slept == [gemini.RATE_LIMIT_BACKOFF_SECONDS]


async def test_paces_when_minute_bucket_full(monkeypatch, keyed, conn, clock):
    paced = RequestBudget(conn, rpm=1, rpd=10, tz="UTC")
    assert paced.try_acquire(NOW)
    use(monkeypatch, FakeClient([summary()]))
    result, status = await gemini.summarize(keyed, paced, "p", {"a"}, NOW)
    assert status == "ok"
    assert len(clock.slept) == 1 and 60 <= clock.slept[0] <= 61


def test_client_has_timeout(monkeypatch):
    captured = {}

    class FakeGenai:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(gemini.genai, "Client", FakeGenai)
    gemini._client_factory("k")
    assert captured["http_options"].timeout == gemini.TIMEOUT_MS


def overloaded(code=503):
    return errors.ServerError(
        code, {"error": {"code": code, "message": "overloaded", "status": "UNAVAILABLE"}}
    )


async def test_503_backs_off_then_succeeds(monkeypatch, keyed, budget, clock):
    client = use(monkeypatch, FakeClient([overloaded(), summary()]))
    result, status = await gemini.summarize(keyed, budget, "p", {"a"}, NOW)
    assert status == "ok"
    assert clock.slept == [gemini.TRANSIENT_BACKOFF_SECONDS[0]]
    assert client.models_used == [keyed.gemini_model, keyed.gemini_model]


async def test_falls_back_to_lite_model_after_repeated_overload(monkeypatch, keyed, budget, clock):
    client = use(monkeypatch, FakeClient([overloaded(503), overloaded(504), summary()]))
    result, status = await gemini.summarize(keyed, budget, "p", {"a"}, NOW)
    assert status == "ok"
    assert client.models_used == [
        keyed.gemini_model,
        keyed.gemini_model,
        "gemini-flash-lite-latest",
    ]
    assert clock.slept == list(gemini.TRANSIENT_BACKOFF_SECONDS)


async def test_no_fallback_configured_retries_primary(monkeypatch, keyed, budget):
    keyed.gemini_fallback_model = None
    client = use(monkeypatch, FakeClient([overloaded(), overloaded(), overloaded()]))
    assert await gemini.summarize(keyed, budget, "p", {"a"}, NOW) == (None, "unavailable")
    assert client.models_used == [keyed.gemini_model] * 3


async def test_takeaway_kept_when_cited_dropped_when_not(monkeypatch, keyed, budget):
    use(
        monkeypatch,
        FakeClient(
            [summary(takeaway=Claim(text="Guidance up, export risk lingers", source_ids=["a"]))]
        ),
    )
    result, _ = await gemini.summarize(keyed, budget, "p", {"a"}, NOW)
    assert result.takeaway.text == "Guidance up, export risk lingers"
    use(monkeypatch, FakeClient([summary(takeaway=Claim(text="Made up", source_ids=["zzz"]))]))
    result, _ = await gemini.summarize(keyed, budget, "p", {"a"}, NOW)
    assert result.takeaway is None


def test_old_summaries_without_takeaway_still_load():
    old = {
        "lean": "bullish",
        "confidence": "low",
        "not_enough_signal": False,
        "substantive_news": True,
        "drivers": [],
        "bull_case": [],
        "bear_case": [],
    }
    assert AISummary.model_validate(old).takeaway is None
