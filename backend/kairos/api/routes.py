import sqlite3
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from kairos.api.deps import get_app_settings, get_conn
from kairos.config import Settings
from kairos.models import Reading
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
