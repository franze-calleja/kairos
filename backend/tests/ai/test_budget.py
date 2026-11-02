from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from kairos.ai.budget import RequestBudget

T0 = datetime(2026, 11, 2, 3, 0, tzinfo=UTC)


def test_budget_rpm(conn):
    b = RequestBudget(conn, rpm=2, rpd=100, tz="UTC")
    assert b.try_acquire(T0)
    assert b.try_acquire(T0 + timedelta(seconds=1))
    assert not b.try_acquire(T0 + timedelta(seconds=2))
    assert b.try_acquire(T0 + timedelta(seconds=61))


def test_budget_rpd_resets_at_local_midnight(conn):
    manila = ZoneInfo("Asia/Manila")
    b = RequestBudget(conn, rpm=10, rpd=1, tz="Asia/Manila")
    late = datetime(2026, 11, 2, 23, 59, tzinfo=manila)
    assert b.try_acquire(late)
    assert not b.try_acquire(late + timedelta(seconds=30))
    assert b.try_acquire(datetime(2026, 11, 3, 0, 1, tzinfo=manila))


def test_usage(conn):
    b = RequestBudget(conn, rpm=10, rpd=200, tz="UTC")
    b.try_acquire(T0)
    assert b.usage(T0) == {"minute": 1, "day": 1, "rpm": 10, "rpd": 200}


def test_seconds_until_slot(conn):
    b = RequestBudget(conn, rpm=2, rpd=3, tz="UTC")
    assert b.seconds_until_slot(T0) == 0
    b.try_acquire(T0)
    b.try_acquire(T0 + timedelta(seconds=10))
    wait = b.seconds_until_slot(T0 + timedelta(seconds=20))
    assert 40 <= wait <= 41
    b.try_acquire(T0 + timedelta(seconds=70))
    assert b.seconds_until_slot(T0 + timedelta(seconds=80)) is None  # daily budget used up
    assert b.day_exhausted(T0 + timedelta(seconds=80)) is True


def test_zero_limits_never_wait(conn):
    assert RequestBudget(conn, rpm=0, rpd=10, tz="UTC").seconds_until_slot(T0) is None
