import pandas as pd

from kairos.analysis.price_context import compute_price_context
from tests.helpers import make_df


def test_flat_series_near_average():
    ctx = compute_price_context(make_df([100.0] * 260))
    assert ctx.label == "near_average"
    assert ctx.ma50 == 100
    assert ctx.pct_vs_ma200 == 0
    assert len(ctx.history) == 252


def test_stretched():
    assert compute_price_context(make_df([100.0] * 250 + [115.0] * 10)).label == "stretched"


def test_below_range():
    assert compute_price_context(make_df([100.0] * 250 + [85.0] * 10)).label == "below_range"


def test_short_history_ma200_none():
    ctx = compute_price_context(make_df([100.0 + (i % 3) for i in range(120)]))
    assert ctx.ma200 is None
    assert ctx.pct_vs_ma200 is None
    assert ctx.label != "insufficient_history"


def test_insufficient_history():
    ctx = compute_price_context(make_df([100.0] * 30))
    assert ctx.label == "insufficient_history"
    assert ctx.ma50 is None
    assert ctx.volatility_30d is None


def test_empty_df_returns_none():
    assert compute_price_context(pd.DataFrame({"Close": [], "Volume": []})) is None


def test_day_change_and_52w():
    ctx = compute_price_context(make_df([100.0] * 258 + [120.0, 110.0]))
    assert round(ctx.day_change_pct, 4) == round((110 / 120 - 1) * 100, 4)
    assert ctx.high_52w == 120.0
    assert round(ctx.pct_from_52w_high, 4) == round((110 / 120 - 1) * 100, 4)


def test_narrow_range_not_below_range():
    # A stock drifting between 100 and 102 all year is near its average, not "below its range".
    ctx = compute_price_context(make_df([100.0 + (i % 3) for i in range(260)]))
    assert ctx.label == "near_average"


def test_near_low_after_big_drop_is_below_range():
    closes = [150.0] * 100 + [100.0] * 150 + [104.0] * 10
    assert compute_price_context(make_df(closes)).label == "below_range"
