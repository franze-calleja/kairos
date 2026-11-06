from datetime import UTC, date, datetime

import pytest

from kairos.analysis.move import compute_move
from tests.helpers import make_df, series

AFTER_CLOSE = datetime(2026, 11, 6, 0, 0, tzinfo=UTC)  # Thu 19:00 NY: 2026-11-05 is complete


def test_notable_drop_with_market_comparison():
    df = make_df(series(last=-9.3), end="2026-11-05")
    mkt = make_df(series(last=-4.4), end="2026-11-05")
    m = compute_move(df, AFTER_CLOSE, mkt)
    assert m.date == date(2026, 11, 5)
    assert m.change_pct == pytest.approx(-9.3, abs=0.01)
    assert 0.4 < m.typical_pct < 0.6
    assert m.notable is True
    assert m.biggest_since is None  # nothing as big in the window
    assert m.market_change_pct == pytest.approx(-4.4, abs=0.01)
    assert m.market_share == "half"  # 4.4 / 9.3 = 0.47
    assert m.market_notable is True


def test_normal_day_not_notable():
    m = compute_move(make_df(series(last=0.4), end="2026-11-05"), AFTER_CLOSE)
    assert m.notable is False and m.market_change_pct is None


def test_one_percent_floor_for_calm_tickers():
    closes = [100.0 + (0.01 if i % 2 else 0) for i in range(59)] + [100.9]  # typical ~0.01%
    assert compute_move(make_df(closes, end="2026-11-05"), AFTER_CLOSE).notable is False


def test_biggest_since_finds_last_larger_same_direction_move():
    closes = series(n=80, last=-9.3)
    closes[30] = closes[29] * 0.88  # -12% earlier
    for i in range(31, 79):
        closes[i] = closes[i - 1] * (1.005 if i % 2 else 0.995)
    closes[79] = closes[78] * 0.907
    df = make_df(closes, end="2026-11-05")
    assert compute_move(df, AFTER_CLOSE).biggest_since == df.index[30].date()


def test_in_progress_session_excluded_during_us_hours():
    df = make_df(series(last=-3.0), end="2026-11-06")  # last row = Fri 2026-11-06
    during = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)  # 10:00 NY
    m = compute_move(df, during)
    assert m.market_open is True and m.date == date(2026, 11, 5)
    after = datetime(2026, 11, 6, 22, 0, tzinfo=UTC)  # 17:00 NY
    m2 = compute_move(df, after)
    assert m2.market_open is False and m2.date == date(2026, 11, 6)


def test_market_share_bands_and_opposite():
    df = make_df(series(last=-5.0), end="2026-11-05")

    def share(market_last):
        return compute_move(df, AFTER_CLOSE, make_df(series(last=market_last), end="2026-11-05"))

    assert share(-4.5).market_share == "market"
    assert share(-1.0).market_share == "ticker"
    assert share(0.6).market_share == "opposite"


def test_market_ticker_itself_and_date_mismatch_omit_market():
    df = make_df(series(last=-4.4), end="2026-11-05")
    own = compute_move(df, AFTER_CLOSE, df, is_market=True)
    assert own.market_change_pct is None and own.market_share is None
    assert own.market_notable is True
    other = make_df(series(last=-4.4), end="2026-11-04")
    assert compute_move(df, AFTER_CLOSE, other).market_change_pct is None


def test_short_history_and_flat_move_are_safe():
    m = compute_move(make_df([100.0] * 10, end="2026-11-05"), AFTER_CLOSE)
    assert m.typical_pct is None and m.notable is False and m.market_share is None
    flat = compute_move(
        make_df([100.0] * 60, end="2026-11-05"),
        AFTER_CLOSE,
        make_df(series(last=-1.0), end="2026-11-05"),
    )
    assert flat.change_pct == 0 and flat.market_share is None
    assert compute_move(make_df([100.0], end="2026-11-05"), AFTER_CLOSE) is None
    assert compute_move(None, AFTER_CLOSE) is None


def test_history_start_recorded_for_short_and_full_histories():
    short = make_df(series(n=60, last=-9.3), end="2026-11-05")
    assert compute_move(short, AFTER_CLOSE).history_start == short.index[0].date()
