"""Positions from logged trades: average cost, gains, and the same dollars in VOO. Price-only."""

import json
import sqlite3
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from pydantic import BaseModel

from kairos.services.closes import close_on, closes_since
from kairos.services.exposure import current_price
from kairos.services.trades import SHARE_EPSILON, Trade, list_trades

MARKET_TICKER = "VOO"
NY = ZoneInfo("America/New_York")
SESSION_CLOSE_NY = time(16, 0)
SAID_WINDOW = timedelta(hours=36)


class Position(BaseModel):
    ticker: str
    shares: float
    avg_cost: float | None
    invested: float  # remaining cost basis
    value: float | None
    gain: float | None  # unrealized, on the remaining position
    gain_pct: float | None
    realized: float
    total_bought: float
    sell_proceeds: float
    return_pct: float | None  # total return incl. sales, vs everything bought
    voo_value: float | None = None  # the same cash flows put into VOO
    voo_proceeds: float | None = None
    voo_pct: float | None = None


def _pct(gain: float, base: float) -> float | None:
    return gain / base * 100 if base else None


def _shadow(trades: list[Trade], voo_closes: pd.Series | None, voo_now: float | None):
    """Replay buys/sells into VOO: same $ in on buys, same fraction out on sells."""
    if voo_closes is None or voo_now is None:
        return None, None
    voo_shares = proceeds = held = 0.0
    for t in trades:
        found = close_on(voo_closes, t.trade_date)
        if found is None:
            return None, None
        voo_price = found[1]
        if t.side == "buy":
            voo_shares += t.shares * t.price / voo_price
            held += t.shares
        else:
            fraction = min(t.shares / held, 1.0) if held else 0.0
            sold = voo_shares * fraction
            voo_shares -= sold
            proceeds += sold * voo_price
            held -= t.shares
    return voo_shares * voo_now, proceeds


def position_for(
    ticker: str,
    trades: list[Trade],
    price_now: float | None,
    voo_closes: pd.Series | None,
    voo_now: float | None,
) -> Position:
    ordered = sorted(trades, key=lambda t: (t.trade_date, t.id))
    shares = basis = realized = bought = proceeds = 0.0
    for t in ordered:
        if t.side == "buy":
            shares += t.shares
            basis += t.shares * t.price
            bought += t.shares * t.price
        else:
            avg = basis / shares if shares else 0.0
            sold = min(t.shares, shares)
            basis -= sold * avg
            realized += sold * (t.price - avg)
            proceeds += sold * t.price
            shares -= sold
    if shares < SHARE_EPSILON:
        shares, basis = 0.0, 0.0
    if shares == 0:  # closed: nothing left to value, gains are all realized
        value, gain = 0.0, None
    else:
        value = shares * price_now if price_now is not None else None
        gain = value - basis if value is not None else None
    voo_value, voo_proceeds = _shadow(ordered, voo_closes, voo_now)
    voo_pct = None
    if voo_value is not None and voo_proceeds is not None and ticker != MARKET_TICKER:
        voo_pct = _pct(voo_value + voo_proceeds - bought, bought)
    return Position(
        ticker=ticker,
        shares=shares,
        avg_cost=basis / shares if shares else None,
        invested=basis,
        value=value,
        gain=gain,
        gain_pct=_pct(gain, basis) if gain is not None else None,
        realized=realized,
        total_bought=bought,
        sell_proceeds=proceeds,
        return_pct=_pct(value + proceeds - bought, bought) if value is not None else None,
        voo_value=voo_value,
        voo_proceeds=voo_proceeds,
        voo_pct=voo_pct,
    )


def totals(positions: list[Position]) -> dict:
    """Across every position, including fully sold ones."""
    bought = sum(p.total_bought for p in positions)
    proceeds = sum(p.sell_proceeds for p in positions)
    invested = sum(p.invested for p in positions)
    have_values = all(p.value is not None for p in positions)
    value = sum(p.value or 0.0 for p in positions) if have_values else None
    have_voo = all(p.voo_value is not None and p.voo_proceeds is not None for p in positions)
    voo_pct = None
    if have_voo and positions:
        voo_total = sum((p.voo_value or 0.0) + (p.voo_proceeds or 0.0) for p in positions)
        voo_pct = _pct(voo_total - bought, bought)
    return {
        "invested": invested,
        "value": value,
        "gain": value - invested if value is not None else None,
        "return_pct": _pct(value + proceeds - bought, bought) if value is not None else None,
        "voo_pct": voo_pct,
    }


def kairos_said(conn: sqlite3.Connection, ticker: str, trade_date: date) -> dict | None:
    """The reading the owner could have seen before that US session closed (max 36h old)."""
    close = datetime.combine(trade_date, SESSION_CLOSE_NY, tzinfo=NY).astimezone(UTC)
    rows = conn.execute(
        "SELECT created_at, lean, ai_status, payload FROM readings WHERE ticker = ? "
        "ORDER BY created_at DESC, id DESC",
        (ticker,),
    ).fetchall()
    for r in rows:
        created = datetime.fromisoformat(r["created_at"])
        if created >= close:
            continue
        if close - created > SAID_WINDOW:
            return None
        try:
            label = (json.loads(r["payload"]).get("price") or {}).get("label")
        except ValueError:
            label = None
        return {"price_label": label, "lean": r["lean"], "ai_status": r["ai_status"]}
    return None


def _pct_change(now: float | None, then: float | None) -> float | None:
    return (now / then - 1) * 100 if now is not None and then else None


async def build_portfolio(conn: sqlite3.Connection, now: datetime) -> dict:
    trades = list_trades(conn)
    if not trades:
        return {"positions": [], "totals": totals([]), "realized": 0.0, "history": []}
    earliest = min(t.trade_date for t in trades)
    voo_closes = await closes_since(MARKET_TICKER, earliest, now)
    voo_now = await current_price(conn, MARKET_TICKER, now)
    by_ticker: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        by_ticker[t.ticker].append(t)
    prices = {tk: await current_price(conn, tk, now) for tk in sorted(by_ticker)}
    positions = [
        position_for(tk, ts, prices[tk], voo_closes, voo_now)
        for tk, ts in sorted(by_ticker.items())
    ]
    history = []
    for t in trades:  # newest first
        row = {
            **t.model_dump(include={"id", "ticker", "side", "trade_date", "shares", "price"}),
            "amount": t.shares * t.price,
            "kairos_said": kairos_said(conn, t.ticker, t.trade_date),
            "since_pct": None,
            "voo_since_pct": None,
        }
        if t.side == "buy":
            row["since_pct"] = _pct_change(prices[t.ticker], t.price)
            voo_then = close_on(voo_closes, t.trade_date) if voo_closes is not None else None
            row["voo_since_pct"] = _pct_change(voo_now, voo_then[1] if voo_then else None)
        history.append(row)
    return {
        "positions": [p for p in positions if p.shares > 0],
        "totals": totals(positions),
        "realized": sum(p.realized for p in positions),
        "history": history,
    }
