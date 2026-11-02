import asyncio
import sqlite3
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from kairos.ai.budget import RequestBudget
from kairos.api.deps import get_app_settings, get_conn
from kairos.config import Settings
from kairos.db import get_meta
from kairos.models import Reading
from kairos.services import scheduler
from kairos.services.discover import latest_discover
from kairos.services.lists import ListName, add_ticker, list_tickers, remove_ticker
from kairos.services.readings import DataUnavailable, UnknownTicker, get_reading
from kairos.services.track_record import stats

router = APIRouter(prefix="/api")
Conn = Annotated[sqlite3.Connection, Depends(get_conn)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]


class TickerIn(BaseModel):
    ticker: str


class ListEntry(BaseModel):
    ticker: str
    lean: str | None = None
    ai_status: str | None = None


def _entry(conn: sqlite3.Connection, ticker: str) -> ListEntry:
    row = conn.execute(
        "SELECT lean, ai_status FROM readings WHERE ticker = ? ORDER BY created_at DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    if row is None:
        return ListEntry(ticker=ticker)
    return ListEntry(ticker=ticker, lean=row["lean"], ai_status=row["ai_status"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/lists")
def get_lists(conn: Conn) -> dict[str, list[ListEntry]]:
    return {
        name: [_entry(conn, t) for t in list_tickers(conn, name)]
        for name in ("holdings", "watching")
    }


@router.post("/lists/{name}", status_code=201)
def post_list(name: ListName, body: TickerIn, conn: Conn) -> ListEntry:
    try:
        ticker = add_ticker(conn, name, body.ticker)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return _entry(conn, ticker)


@router.delete("/lists/{name}/{ticker}", status_code=204)
def delete_list(name: ListName, ticker: str, conn: Conn) -> Response:
    try:
        remove_ticker(conn, name, ticker)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return Response(status_code=204)


@router.get("/readings/{ticker}")
async def get_reading_route(
    ticker: str, conn: Conn, settings: AppSettings, refresh: bool = False
) -> Reading:
    try:
        return await get_reading(settings, conn, ticker, datetime.now(UTC), refresh=refresh)
    except UnknownTicker as e:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {e}") from e
    except DataUnavailable as e:
        raise HTTPException(status_code=503, detail=f"Market data unavailable: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/track-record")
def get_track_record(conn: Conn, ticker: str | None = None) -> dict:
    return stats(conn, ticker)


@router.get("/discover")
def get_discover(conn: Conn) -> dict:
    return latest_discover(conn)


@router.get("/settings")
def get_settings_route(conn: Conn, settings: AppSettings) -> dict:
    budget = RequestBudget(conn, settings.gemini_rpm, settings.gemini_rpd, settings.tz)
    return {
        "gemini_configured": bool(settings.gemini_api_key),
        "finnhub_configured": bool(settings.finnhub_api_key),
        "sec_configured": bool(settings.sec_user_agent),
        "reddit_enabled": settings.reddit_enabled,
        "gemini_model": settings.gemini_model,
        "budget": budget.usage(datetime.now(UTC)),
        "morning_refresh_time": settings.morning_refresh_time,
        "tz": settings.tz,
        "reading_cache_hours": settings.reading_cache_hours,
        "last_morning_run": get_meta(conn, "last_morning_run"),
        "thresholds": {
            "micro_cap_usd": settings.micro_cap_usd,
            "price_spike_pct": settings.price_spike_pct,
            "penny_price": settings.penny_price,
            "low_volume": settings.low_volume,
            "attention_ratio": settings.attention_ratio,
            "attention_min_articles": settings.attention_min_articles,
        },
    }


_background: set[asyncio.Task] = set()


@router.post("/jobs/morning", status_code=202)
async def post_morning_job(request: Request, settings: AppSettings) -> dict[str, str]:
    state = request.app.state
    if state.job_running:
        raise HTTPException(status_code=409, detail="Morning refresh is already running")
    state.job_running = True

    async def run() -> None:
        try:
            await scheduler.run_morning_job(settings)
        finally:
            state.job_running = False

    task = asyncio.create_task(run())
    _background.add(task)
    task.add_done_callback(_background.discard)
    return {"status": "started"}
