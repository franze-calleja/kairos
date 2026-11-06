from datetime import UTC, date, datetime

import pandas as pd
import pytest

from kairos.services.portfolio import position_for, totals
from kairos.services.trades import Trade

T0 = datetime(2026, 11, 6, tzinfo=UTC)
VOO = pd.Series({date(2026, 11, 2): 500.0, date(2026, 11, 3): 400.0, date(2026, 11, 4): 420.0})


def trade(i, side, day, shares, price, ticker="NVDA"):
    return Trade(
        id=i,
        ticker=ticker,
        side=side,
        trade_date=date(2026, 11, day),
        shares=shares,
        price=price,
        created_at=T0,
    )


BUYS = [trade(1, "buy", 2, 1, 100), trade(2, "buy", 3, 1, 200)]
WITH_SELL = [*BUYS, trade(3, "sell", 4, 1, 240)]


def test_average_cost_and_unrealized_gain():
    p = position_for("NVDA", BUYS, 180, None, None)
    assert (p.shares, p.avg_cost, p.invested, p.value, p.gain) == (2, 150, 300, 360, 60)
    assert p.gain_pct == pytest.approx(20.0)
    assert p.return_pct == pytest.approx(20.0)
    assert (p.total_bought, p.sell_proceeds, p.realized) == (300, 0, 0)


def test_sell_realizes_at_average_cost():
    p = position_for("NVDA", WITH_SELL, 180, None, None)
    assert (p.shares, p.invested, p.realized, p.sell_proceeds) == (1, 150, 90, 240)
    assert (p.value, p.gain) == (180, 30)
    assert p.gain_pct == pytest.approx(20.0)
    assert p.return_pct == pytest.approx(40.0)  # (180 + 240 - 300) / 300


def test_same_dollars_in_voo_shadow():
    p = position_for("NVDA", BUYS, 180, VOO, 450)
    assert p.voo_value == pytest.approx(315.0)  # 0.2 + 0.5 VOO at 450
    assert p.voo_pct == pytest.approx(5.0)
    s = position_for("NVDA", WITH_SELL, 180, VOO, 450)
    assert s.voo_proceeds == pytest.approx(147.0)  # half of 0.7 VOO at 420
    assert s.voo_value == pytest.approx(157.5)
    assert s.voo_pct == pytest.approx(1.5)


def test_voo_itself_has_no_voo_pct_and_missing_data_is_none():
    voo_buys = [trade(1, "buy", 2, 1, 500, ticker="VOO")]
    v = position_for("VOO", voo_buys, 450, VOO, 450)
    assert v.voo_pct is None and v.voo_value == pytest.approx(450.0)
    no_price = position_for("NVDA", BUYS, None, VOO, 450)
    assert (no_price.value, no_price.gain, no_price.gain_pct, no_price.return_pct) == (
        None,
        None,
        None,
        None,
    )
    assert position_for("NVDA", BUYS, 180, None, None).voo_pct is None


def test_closed_position_values_and_totals_include_it():
    closed = position_for(
        "AMD",
        [trade(1, "buy", 2, 2, 100, "AMD"), trade(2, "sell", 3, 2, 110, "AMD")],
        None,
        None,
        None,
    )
    assert (closed.shares, closed.value, closed.invested, closed.realized) == (0, 0, 0, 20)
    assert closed.return_pct == pytest.approx(10.0)
    open_ = position_for("NVDA", BUYS, 180, None, None)
    t = totals([open_, closed])
    assert t["invested"] == 300 and t["value"] == 360
    assert t["return_pct"] == pytest.approx((360 + 220 - 500) / 500 * 100)
    assert t["voo_pct"] is None  # no VOO data for either


def test_totals_voo_includes_voo_itself():
    nvda = position_for("NVDA", BUYS, 180, VOO, 450)
    voo = position_for("VOO", [trade(9, "buy", 2, 1, 500, "VOO")], 450, VOO, 450)
    t = totals([nvda, voo])
    assert t["voo_pct"] == pytest.approx((315 + 450 - 800) / 800 * 100)
