import asyncio
import sqlite3
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from kairos.adapters.prices import get_info
from kairos.ai.budget import RequestBudget
from kairos.api.deps import get_app_settings, get_conn
from kairos.config import Settings
from kairos.db import get_meta
from kairos.models import Reading
from kairos.services import scheduler
from kairos.services.backup import BackupFailed, backup_db
from kairos.services.discover import latest_discover
from kairos.services.exposure import compute_exposure
from kairos.services.lists import (
    ListName,
    add_ticker,
    list_tickers,
    remove_ticker,
    set_shares,
    set_thesis,
)
from kairos.services.readings import DataUnavailable, UnknownTicker, get_reading
from kairos.services.track_record import stats
from kairos.tickers import normalize_ticker

router = APIRouter(prefix="/api")
Conn = Annotated[sqlite3.Connection, Depends(get_conn)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]


class TickerIn(BaseModel):
    ticker: str


class ListEntry(BaseModel):
    """A sidebar/overview row: the ticker plus a summary of its latest reading."""

    ticker: str
    lean: str | None = None
    ai_status: str | None = None
    name: str | None = None
    kind: str | None = None
    price: float | None = None
    day_change_pct: float | None = None
    price_label: str | None = None
    next_earnings: str | None = None
    hype_warning: bool | None = None
    updated_at: str | None = None
    shares: float | None = None
    thesis: str | None = None
    thesis_verdict: str | None = None
    move_date: str | None = None
    move_notable: bool | None = None
    move_change_pct: float | None = None
    move_typical_pct: float | None = None
    move_reason: str | None = None
    market_change_pct: float | None = None
    market_notable: bool | None = None
    # Internal: what the latest reading checked; not part of the API response.
    thesis_checked: str | None = Field(default=None, exclude=True)
    thesis_verdict_raw: str | None = Field(default=None, exclude=True)


def _entry(conn: sqlite3.Connection, ticker: str, name: ListName | None = None) -> ListEntry:
    mine = None
    if name:
        mine = conn.execute(
            "SELECT shares, thesis FROM lists WHERE list_name = ? AND ticker = ?", (name, ticker)
        ).fetchone()
    extra = {"shares": mine["shares"], "thesis": mine["thesis"]} if mine else {}
    entry = _summary(conn, ticker)
    if mine and mine["thesis"] and entry.thesis_checked == mine["thesis"]:
        extra["thesis_verdict"] = entry.thesis_verdict_raw
    return entry.model_copy(update=extra)


def _summary(conn: sqlite3.Connection, ticker: str) -> ListEntry:
    row = conn.execute(
        "SELECT lean, ai_status, payload FROM readings WHERE ticker = ? "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    if row is None:
        return ListEntry(ticker=ticker)
    reading = Reading.model_validate_json(row["payload"])
    price = reading.price
    move = reading.move
    ai_reason = reading.ai.move_reason if reading.ai and reading.ai_status == "ok" else None
    return ListEntry(
        ticker=ticker,
        lean=row["lean"],
        ai_status=row["ai_status"],
        name=reading.name,
        kind=reading.kind,
        price=price.last_price if price else None,
        day_change_pct=price.day_change_pct if price else None,
        price_label=price.label if price else None,
        next_earnings=reading.events.next_earnings.isoformat()
        if reading.events.next_earnings
        else None,
        hype_warning=any(f.triggered for f in reading.hype),
        updated_at=reading.created_at.isoformat(),
        thesis_checked=reading.thesis_checked,
        thesis_verdict_raw=reading.ai.thesis_check.verdict
        if reading.ai and reading.ai.thesis_check
        else None,
        move_date=move.date.isoformat() if move else None,
        move_notable=move.notable if move else None,
        move_change_pct=move.change_pct if move else None,
        move_typical_pct=move.typical_pct if move else None,
        move_reason=ai_reason.text if ai_reason else None,
        market_change_pct=move.market_change_pct if move else None,
        market_notable=move.market_notable if move else None,
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/lists")
def get_lists(conn: Conn) -> dict[str, list[ListEntry]]:
    return {
        name: [_entry(conn, t, name) for t in list_tickers(conn, name)]
        for name in ("holdings", "watching")
    }


@router.post("/lists/{name}", status_code=201)
async def post_list(name: ListName, body: TickerIn, conn: Conn) -> ListEntry:
    try:
        symbol = normalize_ticker(body.ticker)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    _, status = await get_info(symbol)
    if status.detail == "unknown ticker":  # a Yahoo outage doesn't block adding
        raise HTTPException(status_code=422, detail=f"Unknown ticker: {symbol}")
    return _entry(conn, add_ticker(conn, name, symbol), name)


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
    try:
        ticker = normalize_ticker(ticker) if ticker else None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
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
        "evening_refresh_time": settings.evening_refresh_time,
        "tz": settings.tz,
        "reading_cache_hours": settings.reading_cache_hours,
        "last_morning_run": get_meta(conn, "last_morning_run"),
        "last_evening_run": get_meta(conn, "last_evening_run"),
        "last_backup": get_meta(conn, "last_backup"),
        "backup_dir": settings.backup_dir,
        "backup_keep": settings.backup_keep,
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


@router.get("/jobs/morning")
def get_morning_job(conn: Conn) -> dict:
    return {**scheduler.job_status(), "last_run": get_meta(conn, "last_morning_run")}


@router.post("/jobs/morning", status_code=202)
async def post_morning_job(settings: AppSettings) -> dict[str, str]:
    if scheduler.job_is_running():
        raise HTTPException(status_code=409, detail="Morning refresh is already running")
    task = asyncio.create_task(scheduler.run_morning_job(settings))
    _background.add(task)
    task.add_done_callback(_background.discard)
    return {"status": "started"}


class SharesIn(BaseModel):
    shares: float | None = None


class ThesisIn(BaseModel):
    thesis: str | None = None


@router.put("/lists/holdings/{ticker}/shares")
def put_shares(ticker: str, body: SharesIn, conn: Conn) -> ListEntry:
    try:
        set_shares(conn, ticker, body.shares)
    except KeyError as e:
        raise HTTPException(
            status_code=404, detail=f"{ticker.upper()} is not in your holdings"
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return _entry(conn, normalize_ticker(ticker), "holdings")


@router.put("/lists/{name}/{ticker}/thesis")
def put_thesis(name: ListName, ticker: str, body: ThesisIn, conn: Conn) -> ListEntry:
    try:
        set_thesis(conn, name, ticker, body.thesis)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"{ticker.upper()} is not in {name}") from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return _entry(conn, normalize_ticker(ticker), name)


@router.get("/exposure")
async def get_exposure(conn: Conn) -> dict:
    return await compute_exposure(conn, datetime.now(UTC))


@router.post("/backup", status_code=201)
def post_backup(conn: Conn, settings: AppSettings) -> dict[str, str]:
    try:
        path = backup_db(settings, conn, datetime.now(UTC))
    except (BackupFailed, OSError, sqlite3.Error) as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {e}") from e
    return {"file": path.name}
