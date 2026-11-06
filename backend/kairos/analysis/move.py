"""How unusual the last completed trading day's move was, and how much was the whole market."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

from kairos.models import Move

NOTABLE_MULTIPLE = 1.5
NOTABLE_MIN_PCT = 1.0
TYPICAL_WINDOW = 30
MARKET_CLOSE_NY = time(16, 15)
SHARE_MARKET = 0.8
SHARE_HALF = 0.35
NY = ZoneInfo("America/New_York")


def _day(ts) -> date:
    return ts.date() if hasattr(ts, "date") else ts


def completed_closes(df: pd.DataFrame, now: datetime) -> pd.Series:
    """Closes of finished sessions: a row dated today (NY) before 16:15 NY is still trading."""
    closes = df["Close"].astype(float).dropna()
    if closes.empty:
        return closes
    ny_now = now.astimezone(NY)
    if _day(closes.index[-1]) == ny_now.date() and ny_now.time() < MARKET_CLOSE_NY:
        return closes.iloc[:-1]
    return closes


def _is_notable(change: float, typical: float | None) -> bool:
    return typical is not None and abs(change) >= max(NOTABLE_MULTIPLE * typical, NOTABLE_MIN_PCT)


def _stats(closes: pd.Series) -> tuple[pd.Series, float, float | None]:
    returns = closes.pct_change().dropna() * 100
    change = float(returns.iloc[-1])
    before = returns.iloc[:-1]
    typical = float(before.iloc[-TYPICAL_WINDOW:].std()) if len(before) >= TYPICAL_WINDOW else None
    return returns, change, typical


def _biggest_since(returns: pd.Series, change: float) -> date | None:
    for ts, r in reversed(list(returns.iloc[:-1].items())):
        if (r < 0) == (change < 0) and abs(r) >= abs(change):
            return _day(ts)
    return None


def _share(change: float, market: float) -> str | None:
    if change == 0:
        return None
    if (market < 0) != (change < 0) and market != 0:
        return "opposite"
    ratio = market / change
    if ratio >= SHARE_MARKET:
        return "market"
    return "half" if ratio >= SHARE_HALF else "ticker"


def compute_move(
    df: pd.DataFrame | None,
    now: datetime,
    market_df: pd.DataFrame | None = None,
    is_market: bool = False,
) -> Move | None:
    if df is None or df.empty:
        return None
    all_closes = df["Close"].astype(float).dropna()
    closes = completed_closes(df, now)
    if len(closes) < 2:
        return None
    returns, change, typical = _stats(closes)
    notable = _is_notable(change, typical)
    move = Move(
        date=_day(closes.index[-1]),
        change_pct=change,
        typical_pct=typical,
        notable=notable,
        biggest_since=_biggest_since(returns, change) if notable else None,
        market_open=len(closes) < len(all_closes),
    )
    if market_df is None or market_df.empty:
        return move
    m_closes = completed_closes(market_df, now)
    if len(m_closes) < 2 or _day(m_closes.index[-1]) != move.date:
        return move
    _, m_change, m_typical = _stats(m_closes)
    update: dict = {"market_notable": _is_notable(m_change, m_typical)}
    if not is_market:
        update |= {"market_change_pct": m_change, "market_share": _share(change, m_change)}
    return move.model_copy(update=update)
