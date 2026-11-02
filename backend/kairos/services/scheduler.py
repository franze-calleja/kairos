"""Morning job: refresh readings for holdings + watchlist, fill outcomes, run Discover.

Scheduling is a make-up check every few minutes rather than a single timer: if today's refresh
time has passed and no run was attempted since, run now. This survives the Mac sleeping
through the refresh time, Docker restarts, and missed timers.
"""

import logging
import sqlite3
from datetime import UTC, datetime
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
_running = False  # one morning run at a time: make-up check and manual button share this


def _now() -> datetime:
    return datetime.now(UTC)


def job_is_running() -> bool:
    return _running


def due_for_makeup(settings: Settings, conn: sqlite3.Connection, now: datetime) -> bool:
    """True when today's (local) refresh time has passed and no run was attempted since."""
    tz = ZoneInfo(settings.tz)
    hour, minute = (int(p) for p in settings.morning_refresh_time.split(":"))
    local_now = now.astimezone(tz)
    scheduled = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if local_now < scheduled:
        return False
    last = get_meta(conn, "last_morning_attempt")
    return last is None or datetime.fromisoformat(last) < scheduled


async def morning_job(settings: Settings, conn: sqlite3.Connection, now: datetime) -> dict:
    # Recorded first, so a run that crashes part-way is not retried every few minutes.
    set_meta(conn, "last_morning_attempt", now.isoformat())
    tickers = sorted(set(list_tickers(conn, "holdings")) | set(list_tickers(conn, "watching")))
    active = settings
    budget = RequestBudget(conn, settings.gemini_rpm, settings.gemini_rpd, settings.tz)
    refreshed, failed = 0, []
    for ticker in tickers:
        try:
            reading = await get_reading(active, conn, ticker, _now(), refresh=True)
        except Exception as e:  # one bad ticker must not stop the morning run
            log.warning("morning refresh failed for %s: %s", ticker, e)
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
    outcomes = await fill_outcomes(settings, conn, now)
    discover = await run_discover(settings, conn, now)
    set_meta(conn, "last_morning_run", now.isoformat())
    return {
        "refreshed": refreshed,
        "failed": failed,
        "outcomes": outcomes,
        "discover": len(discover),
    }


async def run_morning_job(settings: Settings, now: datetime | None = None) -> dict | None:
    """Run the morning job unless one is already running (returns None then)."""
    global _running
    if _running:
        return None
    _running = True
    conn = connect(settings.db_path)
    try:
        return await morning_job(settings, conn, now or _now())
    finally:
        conn.close()
        _running = False


async def makeup_tick(settings: Settings, now: datetime | None = None) -> dict | None:
    now = now or _now()
    conn = connect(settings.db_path)
    try:
        due = due_for_makeup(settings, conn, now)
    finally:
        conn.close()
    if not due:
        return None
    log.info(
        "running morning refresh (scheduled %s %s)", settings.morning_refresh_time, settings.tz
    )
    return await run_morning_job(settings, now)


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
