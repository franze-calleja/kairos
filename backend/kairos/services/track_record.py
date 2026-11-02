"""Track record: what happened 1/5/20 trading days after each counted reading, vs VOO."""

import sqlite3
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from kairos.adapters.prices import get_history
from kairos.config import Settings

HORIZONS = (1, 5, 20)
LEANS = ("bullish", "neutral", "bearish")
BASELINE = "VOO"
SMALL_SAMPLE = 20


def _counted(conn: sqlite3.Connection, tz: ZoneInfo) -> list[sqlite3.Row]:
    """First reading with a lean per (ticker, local calendar day)."""
    rows = conn.execute(
        "SELECT id, ticker, created_at, lean, price_at FROM readings "
        "WHERE lean IS NOT NULL AND price_at IS NOT NULL ORDER BY created_at, id"
    ).fetchall()
    seen: set[tuple[str, date]] = set()
    out = []
    for r in rows:
        key = (r["ticker"], datetime.fromisoformat(r["created_at"]).astimezone(tz).date())
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _close_on_or_before(closes: pd.Series, day: date) -> float | None:
    upto = closes[closes.index.date <= day]
    return float(upto.iloc[-1]) if len(upto) else None


async def fill_outcomes(settings: Settings, conn: sqlite3.Connection, now: datetime) -> int:
    tz = ZoneInfo(settings.tz)
    filled = {
        (r["reading_id"], r["horizon"])
        for r in conn.execute("SELECT reading_id, horizon FROM outcomes")
    }
    todo = [r for r in _counted(conn, tz) if any((r["id"], h) not in filled for h in HORIZONS)]
    if not todo:
        return 0
    cache: dict[str, pd.Series | None] = {}

    async def closes(ticker: str) -> pd.Series | None:
        if ticker not in cache:
            df, _ = await get_history(ticker, period="1y")
            cache[ticker] = df["Close"].astype(float) if df is not None else None
        return cache[ticker]

    baseline = await closes(BASELINE)
    written = 0
    for r in todo:
        series = await closes(r["ticker"])
        if series is None:
            continue
        read_day = datetime.fromisoformat(r["created_at"]).astimezone(tz).date()
        after = series[series.index.date > read_day]
        base_start = _close_on_or_before(baseline, read_day) if baseline is not None else None
        for h in HORIZONS:
            if (r["id"], h) in filled or len(after) < h:
                continue
            price = float(after.iloc[h - 1])
            session_day = after.index[h - 1].date()
            base_end = _close_on_or_before(baseline, session_day) if baseline is not None else None
            base_change = (base_end / base_start - 1) * 100 if base_start and base_end else None
            conn.execute(
                "INSERT INTO outcomes (reading_id, horizon, price, change_pct, "
                "baseline_change_pct, filled_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    r["id"],
                    h,
                    price,
                    (price / r["price_at"] - 1) * 100,
                    base_change,
                    now.astimezone(UTC).isoformat(),
                ),
            )
            written += 1
    conn.commit()
    return written


def stats(conn: sqlite3.Connection, ticker: str | None) -> dict:
    sql = (
        "SELECT r.id, r.lean, o.horizon, o.change_pct, o.baseline_change_pct "
        "FROM outcomes o JOIN readings r ON r.id = o.reading_id"
    )
    params: tuple = ()
    if ticker:
        sql += " WHERE r.ticker = ?"
        params = (ticker.upper(),)
    rows = conn.execute(sql, params).fetchall()
    by_lean: dict[str, dict[str, dict]] = {}
    for lean in LEANS:
        by_lean[lean] = {}
        for h in HORIZONS:
            sel = [r for r in rows if r["lean"] == lean and r["horizon"] == h]
            changes = [r["change_pct"] for r in sel]
            excess = [
                r["change_pct"] - r["baseline_change_pct"]
                for r in sel
                if r["baseline_change_pct"] is not None
            ]
            by_lean[lean][str(h)] = {
                "n": len(sel),
                "avg_change_pct": sum(changes) / len(changes) if changes else None,
                "avg_excess_pct": sum(excess) / len(excess) if excess else None,
                "pct_positive": 100 * sum(c > 0 for c in changes) / len(changes)
                if changes
                else None,
            }
    readings_with_outcomes = len({r["id"] for r in rows})
    return {"by_lean": by_lean, "small_sample": readings_with_outcomes < SMALL_SAMPLE}
