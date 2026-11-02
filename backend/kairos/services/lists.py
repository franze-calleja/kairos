import sqlite3
from datetime import UTC, datetime
from typing import Literal

from kairos.tickers import normalize_ticker

ListName = Literal["holdings", "watching"]


def list_tickers(conn: sqlite3.Connection, name: ListName) -> list[str]:
    rows = conn.execute(
        "SELECT ticker FROM lists WHERE list_name = ? ORDER BY ticker", (name,)
    ).fetchall()
    return [r["ticker"] for r in rows]


def add_ticker(conn: sqlite3.Connection, name: ListName, ticker: str) -> str:
    symbol = normalize_ticker(ticker)
    conn.execute(
        "INSERT OR IGNORE INTO lists (list_name, ticker, added_at) VALUES (?, ?, ?)",
        (name, symbol, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    return symbol


def remove_ticker(conn: sqlite3.Connection, name: ListName, ticker: str) -> None:
    conn.execute(
        "DELETE FROM lists WHERE list_name = ? AND ticker = ?", (name, normalize_ticker(ticker))
    )
    conn.commit()
