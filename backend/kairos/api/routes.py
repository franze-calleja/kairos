import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from kairos.api.deps import get_conn
from kairos.services.lists import ListName, add_ticker, list_tickers, remove_ticker

router = APIRouter(prefix="/api")
Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


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
