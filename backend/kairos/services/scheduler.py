"""Scheduled refreshes.

Morning: readings for holdings + watchlist, track-record outcomes, Discover scan.
Evening (before the US open): readings only.

Scheduling is a make-up check every few minutes rather than fixed timers: if a slot's time has
passed and no run was attempted since, run now. This survives the Mac sleeping through the
refresh time, Docker restarts, and missed timers.
"""

import logging
import sqlite3
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from kairos.ai.budget import RequestBudget
from kairos.config import Settings
from kairos.db import connect, get_meta, set_meta
from kairos.services.discover import run_discover
from kairos.services.lists import list_tickers
from kairos.services.readings import get_reading
from kairos.services.track_record import fill_outcomes

log = logging.getLogger(__name__)
CHECK_EVERY_SECONDS = 300
Slot = Literal["morning", "evening"]
_running = False  # one refresh at a time: make-up checks and the manual button share this
_IDLE = {"kind": None, "phase": None, "done": 0, "total": 0, "current": None, "started_at": None}
_status: dict = dict(_IDLE)


def _now() -> datetime:
    return datetime.now(UTC)


def job_is_running() -> bool:
    return _running


def job_status() -> dict:
    """Progress of the current refresh, for the UI to poll."""
    return {**_status, "running": _running}


def _set(**fields: object) -> None:
    _status.update(fields)


def _reset_status() -> None:
    _status.clear()
    _status.update(_IDLE)


def _today_at(local_now: datetime, hhmm: str) -> datetime:
    hour, minute = (int(p) for p in hhmm.split(":"))
    return local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _attempted_since(conn: sqlite3.Connection, key: str, scheduled: datetime) -> bool:
    last = get_meta(conn, key)
    return last is not None and datetime.fromisoformat(last) >= scheduled


def due_slot(settings: Settings, conn: sqlite3.Connection, now: datetime) -> Slot | None:
    """Which refresh should run now, if any.

    Morning is due from its time until the evening time; evening from its time until midnight.
    Each runs once per day; a missed slot is made up as soon as the app is awake in its window.
    """
    local_now = now.astimezone(ZoneInfo(settings.tz))
    if settings.evening_refresh_time:
        evening = _today_at(local_now, settings.evening_refresh_time)
        if local_now >= evening:
            if _attempted_since(conn, "last_evening_attempt", evening):
                return None
            return "evening"
    morning = _today_at(local_now, settings.morning_refresh_time)
    if local_now >= morning and not _attempted_since(conn, "last_morning_attempt", morning):
        return "morning"
    return None


def due_for_makeup(settings: Settings, conn: sqlite3.Connection, now: datetime) -> bool:
    return due_slot(settings, conn, now) == "morning"


async def _refresh_readings(settings: Settings, conn: sqlite3.Connection) -> tuple[int, list[str]]:
    tickers = sorted(set(list_tickers(conn, "holdings")) | set(list_tickers(conn, "watching")))
    _set(phase="readings", done=0, total=len(tickers), current=None)
    active = settings
    budget = RequestBudget(conn, settings.gemini_rpm, settings.gemini_rpd, settings.tz)
    refreshed, failed = 0, []
    for i, ticker in enumerate(tickers):
        _set(done=i, current=ticker)
        try:
            reading = await get_reading(active, conn, ticker, _now(), refresh=True)
        except Exception as e:  # one bad ticker must not stop the run
            log.warning("refresh failed for %s: %s", ticker, e)
            failed.append(ticker)
            continue
        refreshed += 1
        if (
            reading.ai_status == "budget_exhausted"
            and active.gemini_rpd != 0
            and budget.day_exhausted(_now())
        ):
            # Daily budget used up: remaining tickers still get computed-only readings.
            active = settings.model_copy(update={"gemini_rpd": 0})
    _set(done=len(tickers), current=None)
    return refreshed, failed


async def morning_job(settings: Settings, conn: sqlite3.Connection, now: datetime) -> dict:
    # Recorded first, so a run that crashes part-way is not retried every few minutes.
    set_meta(conn, "last_morning_attempt", now.isoformat())
    _set(kind="morning", started_at=now.isoformat())
    try:
        refreshed, failed = await _refresh_readings(settings, conn)
        _set(phase="outcomes")
        outcomes = await fill_outcomes(settings, conn, now)
        _set(phase="discover", done=0, total=0)
        discover = await run_discover(
            settings, conn, now, on_progress=lambda done, total: _set(done=done, total=total)
        )
        set_meta(conn, "last_morning_run", now.isoformat())
        return {
            "refreshed": refreshed,
            "failed": failed,
            "outcomes": outcomes,
            "discover": len(discover),
        }
    finally:
        _reset_status()


async def evening_job(settings: Settings, conn: sqlite3.Connection, now: datetime) -> dict:
    """Readings only, before the US open: no Discover scan, no track-record outcomes."""
    set_meta(conn, "last_evening_attempt", now.isoformat())
    _set(kind="evening", started_at=now.isoformat())
    try:
        refreshed, failed = await _refresh_readings(settings, conn)
        set_meta(conn, "last_evening_run", now.isoformat())
        return {"refreshed": refreshed, "failed": failed}
    finally:
        _reset_status()


async def run_job(settings: Settings, slot: Slot, now: datetime | None = None) -> dict | None:
    """Run a refresh unless one is already running (returns None then)."""
    global _running
    if _running:
        return None
    _running = True
    conn = connect(settings.db_path)
    try:
        job = morning_job if slot == "morning" else evening_job
        return await job(settings, conn, now or _now())
    finally:
        conn.close()
        _running = False


async def run_morning_job(settings: Settings, now: datetime | None = None) -> dict | None:
    return await run_job(settings, "morning", now)


async def makeup_tick(settings: Settings, now: datetime | None = None) -> dict | None:
    now = now or _now()
    conn = connect(settings.db_path)
    try:
        slot = due_slot(settings, conn, now)
    finally:
        conn.close()
    if slot is None:
        return None
    log.info("running %s refresh (%s)", slot, settings.tz)
    return await run_job(settings, slot, now)


def build_scheduler(settings: Settings) -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=settings.tz)
    sched.add_job(
        makeup_tick,
        IntervalTrigger(seconds=CHECK_EVERY_SECONDS, timezone=settings.tz),
        args=[settings],
        id="morning-makeup",
        next_run_time=datetime.now(ZoneInfo(settings.tz)),  # check right away on startup
        coalesce=True,
        max_instances=1,
        misfire_grace_time=None,
    )
    return sched
