from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from kairos.db import get_meta
from kairos.services import scheduler
from kairos.services.lists import add_ticker

NOW = datetime(2026, 11, 2, 23, 0, tzinfo=UTC)


class Calls:
    def __init__(self, fail=(), exhausted_after=None):
        self.built, self.fail, self.exhausted_after = [], set(fail), exhausted_after
        self.outcomes = self.discover = 0
        self.rpd_seen = []

    async def get_reading(self, settings, conn, ticker, now, refresh=False):
        assert refresh is True
        self.built.append(ticker)
        self.rpd_seen.append(settings.gemini_rpd)
        if ticker in self.fail:
            raise RuntimeError("boom")
        status = (
            "budget_exhausted"
            if self.exhausted_after and len(self.built) >= self.exhausted_after
            else "ok"
        )
        return SimpleNamespace(ai_status=status)

    async def fill_outcomes(self, settings, conn, now):
        self.outcomes += 1
        return 3

    async def run_discover(self, settings, conn, now):
        self.discover += 1
        return [1, 2]


@pytest.fixture
def calls(monkeypatch):
    def install(c):
        for name in ("get_reading", "fill_outcomes", "run_discover"):
            monkeypatch.setattr(scheduler, name, getattr(c, name))
        return c

    return install


async def test_morning_job_continues_after_failure(settings, conn, calls):
    c = calls(Calls(fail={"BAD"}))
    add_ticker(conn, "holdings", "NVDA")
    add_ticker(conn, "holdings", "BAD")
    result = await scheduler.morning_job(settings, conn, NOW)
    assert result == {"refreshed": 1, "failed": ["BAD"], "outcomes": 3, "discover": 2}
    assert c.outcomes == 1 and c.discover == 1
    assert get_meta(conn, "last_morning_run") == NOW.isoformat()


async def test_morning_job_dedupes_lists(settings, conn, calls):
    c = calls(Calls())
    add_ticker(conn, "holdings", "NVDA")
    add_ticker(conn, "watching", "NVDA")
    add_ticker(conn, "watching", "AMD")
    await scheduler.morning_job(settings, conn, NOW)
    assert c.built == ["AMD", "NVDA"]


async def test_morning_job_stops_ai_only_when_daily_budget_used(settings, conn, calls, monkeypatch):
    monkeypatch.setattr(scheduler, "_now", lambda: NOW)
    c = calls(Calls(exhausted_after=1))
    for t in ("AAA", "BBB", "CCC"):
        add_ticker(conn, "holdings", t)
    settings.gemini_rpd = 2
    conn.executemany("INSERT INTO budget (ts) VALUES (?)", [(NOW.isoformat(),)] * 2)
    await scheduler.morning_job(settings, conn, NOW)
    assert c.rpd_seen == [2, 0, 0]


async def test_morning_job_keeps_ai_after_per_minute_limit(settings, conn, calls, monkeypatch):
    monkeypatch.setattr(scheduler, "_now", lambda: NOW)
    c = calls(Calls(exhausted_after=1))
    for t in ("AAA", "BBB", "CCC"):
        add_ticker(conn, "holdings", t)
    await scheduler.morning_job(settings, conn, NOW)
    assert c.rpd_seen == [settings.gemini_rpd] * 3


async def test_morning_job_uses_fresh_clock_per_ticker(settings, conn, calls, monkeypatch):
    ticks = iter(NOW + timedelta(minutes=i) for i in range(10))
    monkeypatch.setattr(scheduler, "_now", lambda: next(ticks))
    seen = []
    calls(Calls())

    async def record(settings, conn, ticker, now, refresh=False):
        seen.append(now)
        return SimpleNamespace(ai_status="ok")

    monkeypatch.setattr(scheduler, "get_reading", record)
    add_ticker(conn, "holdings", "AAA")
    add_ticker(conn, "holdings", "BBB")
    await scheduler.morning_job(settings, conn, NOW)
    assert len(set(seen)) == 2


def test_start_scheduler_uses_time_and_tz(settings):
    settings.morning_refresh_time, settings.tz = "06:45", "Asia/Manila"
    sched = scheduler.build_scheduler(settings)
    job = sched.get_jobs()[0]
    assert str(job.trigger.timezone) == "Asia/Manila"
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "6" and fields["minute"] == "45"
