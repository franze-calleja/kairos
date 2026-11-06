"""The owner's logged buys and sells. Local only; never sent to the AI."""

import math
import sqlite3
from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from kairos.tickers import normalize_ticker

SHARE_EPSILON = 0.0001  # display rounding: leftovers this small count as zero
MIN_DATE = date(2000, 1, 1)
NY = ZoneInfo("America/New_York")


class TradeError(ValueError):
    pass


class Trade(BaseModel):
    id: int
    ticker: str
    side: Literal["buy", "sell"]
    trade_date: date
    shares: float
    price: float
    created_at: datetime


def ny_today(now: datetime) -> date:
    return now.astimezone(NY).date()


def _row(r: sqlite3.Row) -> Trade:
    return Trade(
        id=r["id"],
        ticker=r["ticker"],
        side=r["side"],
        trade_date=date.fromisoformat(r["trade_date"]),
        shares=r["shares"],
        price=r["price"],
        created_at=datetime.fromisoformat(r["created_at"]),
    )


def list_trades(conn: sqlite3.Connection, ticker: str | None = None) -> list[Trade]:
    """Newest first."""
    where, args = ("WHERE ticker = ?", (normalize_ticker(ticker),)) if ticker else ("", ())
    rows = conn.execute(
        f"SELECT * FROM trades {where} ORDER BY trade_date DESC, id DESC", args
    ).fetchall()
    return [_row(r) for r in rows]


def _chronological(trades: list[Trade]) -> list[Trade]:
    return sorted(trades, key=lambda t: (t.trade_date, t.id))


def held_shares(trades: list[Trade]) -> float:
    held = 0.0
    for t in _chronological(trades):
        held += t.shares if t.side == "buy" else -t.shares
    return 0.0 if held < SHARE_EPSILON else held


def _first_shortfall(trades: list[Trade]) -> tuple[Trade, float] | None:
    """The first sell that exceeds what was held at that point, with the amount held before it."""
    held = 0.0
    for t in _chronological(trades):
        if t.side == "sell" and t.shares > held + SHARE_EPSILON:
            return t, held
        held += t.shares if t.side == "buy" else -t.shares
    return None


def _fmt(shares: float) -> str:
    return f"{shares:.4f}".rstrip("0").rstrip(".") or "0"


def add_trade(
    conn: sqlite3.Connection,
    ticker: str,
    side: str,
    trade_date: date,
    price: float,
    now: datetime,
    shares: float | None = None,
    amount: float | None = None,
) -> Trade:
    symbol = normalize_ticker(ticker)
    if side not in ("buy", "sell"):
        raise TradeError("Side must be buy or sell")
    if trade_date > ny_today(now):
        raise TradeError("That date is in the future (dates are US market days)")
    if trade_date < MIN_DATE:
        raise TradeError("Dates before 2000 are not supported")
    if not (math.isfinite(price) and price > 0):
        raise TradeError("Price must be more than 0")
    if shares is not None and amount is not None:
        raise TradeError("Give shares or a $ amount, not both")
    if shares is None and amount is None:
        raise TradeError("Give shares or a $ amount")
    qty = shares if shares is not None else amount / price  # type: ignore[operator]
    if not (math.isfinite(qty) and qty > 0):
        raise TradeError("Shares or amount must be more than 0")

    existing = list_trades(conn, symbol)
    if side == "sell":
        held = 0.0
        for t in _chronological(existing):
            if t.trade_date > trade_date:
                break
            held += t.shares if t.side == "buy" else -t.shares
        if qty > held + SHARE_EPSILON:
            raise TradeError(f"You only held {_fmt(held)} {symbol} on {trade_date.isoformat()}")
        qty = min(qty, held)  # within display rounding: sell exactly what was held
    candidate = Trade(
        id=10**12,  # sorts after existing trades on the same date
        ticker=symbol,
        side=side,  # type: ignore[arg-type]
        trade_date=trade_date,
        shares=qty,
        price=price,
        created_at=now,
    )
    shortfall = _first_shortfall([*existing, candidate])
    if shortfall:
        bad, held = shortfall
        raise TradeError(
            f"A sale on {bad.trade_date.isoformat()} would be more than the "
            f"{_fmt(held)} {symbol} held then"
        )
    cur = conn.execute(
        "INSERT INTO trades (ticker, side, trade_date, shares, price, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (symbol, side, trade_date.isoformat(), qty, price, now.astimezone(UTC).isoformat()),
    )
    conn.commit()
    return candidate.model_copy(update={"id": cur.lastrowid})


def delete_trade(conn: sqlite3.Connection, trade_id: int) -> None:
    row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    if row is None:
        raise KeyError(trade_id)
    trade = _row(row)
    remaining = [t for t in list_trades(conn, trade.ticker) if t.id != trade_id]
    shortfall = _first_shortfall(remaining)
    if shortfall:
        bad, _ = shortfall
        raise TradeError(
            f"Can't delete this buy: the sale on {bad.trade_date.isoformat()} needs those shares."
            " Delete the sale first."
        )
    conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()


def net_shares(conn: sqlite3.Connection, ticker: str) -> float | None:
    """Shares held from logged trades, or None when the ticker has no trades."""
    trades = list_trades(conn, ticker)
    return held_shares(trades) if trades else None
