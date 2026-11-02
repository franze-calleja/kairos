"""Morning job: refresh readings for holdings + watchlist, fill outcomes, run Discover."""

import logging
import sqlite3
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from kairos.ai.budget import RequestBudget
from kairos.config import Settings
from kairos.db import connect, set_meta
from kairos.services.discover import run_discover
from kairos.services.lists import list_tickers
from kairos.services.readings import get_reading
from kairos.services.track_record import fill_outcomes

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


async def morning_job(settings: Settings, conn: sqlite3.Connection, now: datetime) -> dict:
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


async def run_morning_job(settings: Settings) -> dict:
    conn = connect(settings.db_path)
    try:
        return await morning_job(settings, conn, datetime.now(UTC))
    finally:
        conn.close()


def build_scheduler(settings: Settings) -> AsyncIOScheduler:
    hour, minute = (int(p) for p in settings.morning_refresh_time.split(":"))
    sched = AsyncIOScheduler(timezone=settings.tz)
    sched.add_job(
        run_morning_job,
        CronTrigger(hour=hour, minute=minute, timezone=settings.tz),
        args=[settings],
        id="morning",
        coalesce=True,
        misfire_grace_time=3600,
    )
    return sched
