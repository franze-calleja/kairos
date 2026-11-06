from datetime import UTC, date, datetime

import pytest

from kairos.services.trades import (
    TradeError,
    add_trade,
    delete_trade,
    list_trades,
    net_shares,
)

NOW = datetime(2026, 11, 6, 20, 0, tzinfo=UTC)  # 15:00 NY, Fri Nov 6


def buy(conn, day, price=100.0, **kw):
    return add_trade(conn, "NVDA", "buy", day, price=price, now=NOW, **kw)


def test_buy_by_amount_computes_shares(conn):
    t = add_trade(conn, "nvda", "buy", date(2026, 11, 5), price=181.6, now=NOW, amount=25.0)
    assert t.ticker == "NVDA" and t.side == "buy"
    assert t.shares == pytest.approx(25 / 181.6)


def test_exactly_one_of_shares_or_amount(conn):
    with pytest.raises(TradeError, match="not both"):
        buy(conn, date(2026, 11, 5), shares=1.0, amount=10.0)
    with pytest.raises(TradeError, match="shares or a \\$ amount"):
        buy(conn, date(2026, 11, 5))


def test_rejects_future_and_ancient_dates_and_bad_numbers(conn):
    with pytest.raises(TradeError, match="future"):
        buy(conn, date(2026, 11, 7), shares=1.0)
    with pytest.raises(TradeError):
        buy(conn, date(1999, 12, 31), shares=1.0)
    with pytest.raises(TradeError):
        buy(conn, date(2026, 11, 5), price=0, shares=1.0)
    with pytest.raises(TradeError):
        buy(conn, date(2026, 11, 5), shares=-1.0)
    with pytest.raises(TradeError):
        add_trade(conn, "NVDA", "hold", date(2026, 11, 5), price=1.0, now=NOW, shares=1.0)
    assert list_trades(conn) == []


def test_sell_cannot_exceed_holdings_on_that_date(conn):
    buy(conn, date(2026, 11, 3), shares=1.0)
    with pytest.raises(TradeError, match="You only held 0 NVDA on 2026-11-02"):
        add_trade(conn, "NVDA", "sell", date(2026, 11, 2), price=100.0, now=NOW, shares=0.5)


def test_sell_within_epsilon_is_capped_and_closes_position(conn):
    b = buy(conn, date(2026, 11, 3), price=181.6, amount=25.0)
    s = add_trade(
        conn,
        "NVDA",
        "sell",
        date(2026, 11, 5),
        price=190.0,
        now=NOW,
        shares=round(25 / 181.6, 4) + 0.00004,
    )
    assert s.shares == pytest.approx(b.shares)
    assert net_shares(conn, "NVDA") == 0.0


def test_delete_buy_that_a_later_sell_needs_is_rejected(conn):
    b = buy(conn, date(2026, 11, 2), shares=1.0)
    add_trade(conn, "NVDA", "sell", date(2026, 11, 4), price=110.0, now=NOW, shares=1.0)
    with pytest.raises(TradeError):
        delete_trade(conn, b.id)
    assert len(list_trades(conn)) == 2


def test_delete_missing_trade_raises_key_error(conn):
    with pytest.raises(KeyError):
        delete_trade(conn, 999)


def test_net_shares_none_without_trades_and_list_order(conn):
    assert net_shares(conn, "VOO") is None
    first = buy(conn, date(2026, 11, 2), shares=1.0)
    second = buy(conn, date(2026, 11, 4), shares=2.0)
    assert [t.id for t in list_trades(conn)] == [second.id, first.id]
    assert net_shares(conn, "nvda") == pytest.approx(3.0)
