import math

import pandas as pd

from kairos.models import PriceContext, PricePoint


def _pct(a: float, b: float | None) -> float | None:
    return None if b is None or b == 0 else (a / b - 1) * 100


def compute_price_context(df: pd.DataFrame) -> PriceContext | None:
    if df is None or df.empty:
        return None
    closes = df["Close"].astype(float).dropna()
    if closes.empty:
        return None
    n = len(closes)
    last = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if n >= 2 else None
    ma50 = float(closes.iloc[-50:].mean()) if n >= 50 else None
    ma200 = float(closes.iloc[-200:].mean()) if n >= 200 else None
    window = closes.iloc[-252:]
    high, low = float(window.max()), float(window.min())
    vol = None
    if n >= 31:
        vol = float(closes.iloc[-31:].pct_change().dropna().std() * math.sqrt(252) * 100)

    pct50, pct200 = _pct(last, ma50), _pct(last, ma200)
    if n < 50:
        label = "insufficient_history"
    elif (pct50 is not None and pct50 >= 10) or (pct200 is not None and pct200 >= 20):
        label = "stretched"
    elif (pct200 is not None and pct200 <= -10) or (high >= low * 1.2 and last <= low * 1.10):
        # "Near the 52-week low" only counts when the year's range is meaningful (>= 20%).
        label = "below_range"
    else:
        label = "near_average"

    return PriceContext(
        last_price=last,
        day_change_pct=_pct(last, prev),
        ma50=ma50,
        ma200=ma200,
        pct_vs_ma50=pct50,
        pct_vs_ma200=pct200,
        high_52w=high,
        low_52w=low,
        pct_from_52w_high=_pct(last, high) or 0.0,
        volatility_30d=vol,
        label=label,
        history=[PricePoint(date=ts.date(), close=float(c)) for ts, c in window.items()],
    )
