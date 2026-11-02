import math
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


MAX_THESIS_CHARS = 200


def _require(conn: sqlite3.Connection, name: ListName, symbol: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM lists WHERE list_name = ? AND ticker = ?", (name, symbol)
    ).fetchone()
    if row is None:
        raise KeyError(f"{symbol} is not in {name}")


def set_shares(conn: sqlite3.Connection, ticker: str, shares: float | None) -> None:
    symbol = normalize_ticker(ticker)
    _require(conn, "holdings", symbol)
    if shares is not None and (not math.isfinite(shares) or shares < 0):
        raise ValueError("Shares must be a number of 0 or more")
    conn.execute(
        "UPDATE lists SET shares = ? WHERE list_name = 'holdings' AND ticker = ?",
        (shares or None, symbol),
    )
    conn.commit()


def set_thesis(conn: sqlite3.Connection, name: ListName, ticker: str, thesis: str | None) -> None:
    symbol = normalize_ticker(ticker)
    _require(conn, name, symbol)
    text = " ".join((thesis or "").split())  # trims and collapses newlines/whitespace
    if len(text) > MAX_THESIS_CHARS:
        raise ValueError(f"Reason must be {MAX_THESIS_CHARS} characters or fewer")
    conn.execute(
        "UPDATE lists SET thesis = ? WHERE list_name = ? AND ticker = ?",
        (text or None, name, symbol),
    )
    conn.commit()


def get_thesis(conn: sqlite3.Connection, ticker: str) -> str | None:
    row = conn.execute(
        "SELECT thesis FROM lists WHERE ticker = ? AND thesis IS NOT NULL "
        "ORDER BY list_name = 'holdings' DESC LIMIT 1",
        (normalize_ticker(ticker),),
    ).fetchone()
    return row["thesis"] if row else None
