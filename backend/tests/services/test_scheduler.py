from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from kairos.db import get_meta, set_meta
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

    async def run_discover(self, settings, conn, now, on_progress=None):
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


MANILA = ZoneInfo("Asia/Manila")


def manila(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=MANILA)


@pytest.fixture
def manila_settings(settings):
    settings.tz, settings.morning_refresh_time = "Asia/Manila", "07:00"
    return settings


def test_not_due_before_refresh_time(manila_settings, conn):
    assert scheduler.due_for_makeup(manila_settings, conn, manila(3, 6, 59)) is False


def test_due_after_refresh_time_when_never_run(manila_settings, conn):
    assert scheduler.due_for_makeup(manila_settings, conn, manila(3, 8, 0)) is True


def test_due_when_last_attempt_was_yesterday(manila_settings, conn):
    set_meta(conn, "last_morning_attempt", manila(2, 7, 0).isoformat())
    assert scheduler.due_for_makeup(manila_settings, conn, manila(3, 9, 30)) is True


def test_not_due_when_already_attempted_after_refresh_time(manila_settings, conn):
    set_meta(conn, "last_morning_attempt", manila(3, 7, 2).isoformat())
    assert scheduler.due_for_makeup(manila_settings, conn, manila(3, 23, 0)) is False


def test_due_compares_in_local_time(manila_settings, conn):
    # 07:30 Manila on Nov 3 is 23:30 UTC on Nov 2 — "today" must mean the Manila day.
    set_meta(conn, "last_morning_attempt", manila(2, 7, 0).isoformat())
    now_utc = datetime(2026, 11, 2, 23, 30, tzinfo=UTC)
    assert scheduler.due_for_makeup(manila_settings, conn, now_utc) is True


async def test_morning_job_records_attempt_at_start(settings, conn, calls):
    calls(Calls(fail={"BAD"}))
    add_ticker(conn, "holdings", "BAD")
    await scheduler.morning_job(settings, conn, NOW)
    assert get_meta(conn, "last_morning_attempt") == NOW.isoformat()


async def test_makeup_tick_runs_once_per_day(manila_settings, monkeypatch):
    runs = []

    async def fake_job(settings, conn, now):
        runs.append(now)
        set_meta(conn, "last_morning_attempt", now.isoformat())
        return {"refreshed": 0}

    monkeypatch.setattr(scheduler, "morning_job", fake_job)
    from kairos.db import connect, init_db

    init_db(connect(manila_settings.db_path), manila_settings)
    assert await scheduler.makeup_tick(manila_settings, manila(3, 6, 0)) is None
    assert await scheduler.makeup_tick(manila_settings, manila(3, 8, 0)) == {"refreshed": 0}
    assert await scheduler.makeup_tick(manila_settings, manila(3, 8, 5)) is None
    assert len(runs) == 1


async def test_run_morning_job_skips_when_already_running(settings, monkeypatch):
    monkeypatch.setattr(scheduler, "_running", True)
    assert await scheduler.run_morning_job(settings) is None


async def test_scheduler_checks_every_five_minutes_starting_now(manila_settings):
    sched = scheduler.build_scheduler(manila_settings)
    sched.start(paused=True)
    try:
        (job,) = sched.get_jobs()
        assert job.id == "morning-makeup"
        assert job.trigger.interval.total_seconds() == 300
        assert job.next_run_time <= datetime.now(UTC) + timedelta(seconds=5)
    finally:
        sched.shutdown(wait=False)


def test_status_idle_by_default():
    status = scheduler.job_status()
    assert status["running"] is False
    assert status["phase"] is None


async def test_morning_job_reports_progress(settings, conn, calls, monkeypatch):
    seen = []
    c = calls(Calls())

    async def record(settings, conn, ticker, now, refresh=False):
        seen.append({k: scheduler.job_status()[k] for k in ("phase", "done", "total", "current")})
        return SimpleNamespace(ai_status="ok")

    async def discover(settings, conn, now, on_progress=None):
        on_progress(120, 503)
        seen.append({k: scheduler.job_status()[k] for k in ("phase", "done", "total")})
        return []

    monkeypatch.setattr(scheduler, "get_reading", record)
    monkeypatch.setattr(scheduler, "run_discover", discover)
    add_ticker(conn, "holdings", "AAA")
    add_ticker(conn, "holdings", "BBB")
    await scheduler.morning_job(settings, conn, NOW)
    assert seen == [
        {"phase": "readings", "done": 0, "total": 2, "current": "AAA"},
        {"phase": "readings", "done": 1, "total": 2, "current": "BBB"},
        {"phase": "discover", "done": 120, "total": 503},
    ]
    assert scheduler.job_status()["phase"] is None
    assert c.outcomes == 1
