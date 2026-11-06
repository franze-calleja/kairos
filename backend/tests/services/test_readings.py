from collections import Counter
from datetime import timedelta

import pytest

from kairos.services import readings
from kairos.services.readings import UnknownTicker, build_reading, get_reading
from tests.helpers import series
from tests.services.fakes import NOW, Sources


@pytest.fixture
def src(monkeypatch):
    return Sources().install(monkeypatch)


def health(reading):
    return {s.name: s.status for s in reading.data_health}


async def test_stock_reading_full(settings, conn, src):
    r = await build_reading(settings, conn, "nvda", NOW)
    assert r.ticker == "NVDA"
    assert r.name == "NVIDIA Corporation"
    assert r.kind == "stock"
    assert r.ai_status == "ok"
    assert r.ai.lean == "bullish"
    assert r.price.label == "near_average"
    assert len(r.hype) == 6
    assert conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0] == 1
    row = conn.execute("SELECT lean, price_at FROM readings").fetchone()
    assert row["lean"] == "bullish" and row["price_at"] == 100.0


async def test_unknown_ticker_raises(settings, conn, src):
    with pytest.raises(UnknownTicker):
        await build_reading(settings, conn, "XYZQQ", NOW)


async def test_thin_news_skips_gemini(settings, conn, src):
    src.finnhub_per_ticker, src.google_per_ticker = 1, 1
    r = await build_reading(settings, conn, "NVDA", NOW)
    assert r.ai_status == "not_enough_signal"
    assert r.ai is None
    assert src.summarize_calls == 0
    assert conn.execute("SELECT lean FROM readings").fetchone()["lean"] is None


async def test_ai_unavailable_still_has_computed(settings, conn, src):
    src.summary_status = "unavailable"
    r = await build_reading(settings, conn, "NVDA", NOW)
    assert r.ai_status == "unavailable"
    assert r.ai is None
    assert r.price is not None and r.events is not None and r.quick.market_cap == 4.5e12
    assert len(r.hype) == 6
    assert health(r)["gemini"] == "error"


async def test_etf_weighted_lookthrough(settings, conn, src):
    src.finnhub_per_ticker, src.google_per_ticker = 20, 0
    r = await build_reading(settings, conn, "QQQ", NOW)
    assert r.kind == "etf"
    holdings = {h.symbol: h.weight for h in src.holdings["QQQ"]}
    total = sum(holdings.values())
    counts = Counter(n.related_ticker for n in r.sources)
    for symbol, weight in holdings.items():
        assert counts[symbol] <= max(1, round(weight / total * 30))
    for n in r.sources:
        if n.related_ticker in holdings:
            assert n.weight == holdings[n.related_ticker]
    assert r.quick.top_holdings[0].symbol == "NVDA"
    assert "NVDA" in src.news_tickers and "QQQ" not in src.news_tickers


async def test_etf_market_news_included(settings, conn, src):
    src.google_per_ticker = 3
    r = await build_reading(settings, conn, "QQQ", NOW)
    market = [n for n in r.sources if n.related_ticker == "MARKET"]
    assert market and all(n.weight == 0.05 for n in market)


async def test_etf_no_holdings_fallback(settings, conn, src):
    src.holdings["QQQ"] = []
    r = await build_reading(settings, conn, "QQQ", NOW)
    assert "QQQ" in src.news_tickers
    assert health(r)["yfinance"] == "error"


async def test_finnhub_missing_still_reads(settings, conn, src):
    src.finnhub_status = "not_configured"
    src.google_per_ticker = 5
    r = await build_reading(settings, conn, "NVDA", NOW)
    assert r.ai_status == "ok"
    assert health(r)["finnhub"] == "not_configured"


async def test_prompt_excludes_portfolio(settings, conn, src):
    from kairos.services.lists import add_ticker

    add_ticker(conn, "watching", "PLTR")
    await build_reading(settings, conn, "NVDA", NOW)
    assert "PLTR" not in src.last_prompt


async def test_cache_hit_and_refresh(settings, conn, src):
    first = await get_reading(settings, conn, "NVDA", NOW)
    calls = src.calls
    again = await get_reading(settings, conn, "NVDA", NOW + timedelta(hours=1))
    assert again.created_at == first.created_at
    assert src.calls == calls
    fresh = await get_reading(settings, conn, "NVDA", NOW + timedelta(hours=1), refresh=True)
    assert fresh.created_at > first.created_at
    stale = await get_reading(settings, conn, "NVDA", NOW + timedelta(hours=6))
    assert stale.created_at == NOW + timedelta(hours=6)


def test_latest_reading_none(conn):
    assert readings.latest_reading(conn, "NVDA") is None


async def test_attention_uses_uncapped_news(settings, conn, src):
    src.finnhub_per_ticker, src.google_per_ticker = 50, 0
    r = await build_reading(settings, conn, "NVDA", NOW)
    assert len(r.sources) == 40
    # 50 articles spread over Nov 2/1/Oct 31: 28 recent + 22 baseline (the capped 40 would give 12)
    assert r.hype[0].value == "28 articles in 2 days vs 4.4/day before"


async def test_event_dates_use_local_timezone(settings, conn, src):
    # 07:30 in Manila on Nov 3 is still Nov 2 in UTC.
    from datetime import UTC, date, datetime

    settings.tz = "Asia/Manila"
    src.next_earnings = date(2026, 11, 10)
    now = datetime(2026, 11, 2, 23, 30, tzinfo=UTC)
    r = await build_reading(settings, conn, "NVDA", now)
    assert src.earnings_today == date(2026, 11, 3)
    assert r.events.earnings_within_7d is True  # Nov 3 -> Nov 10 is 7 days


async def test_reading_checks_thesis_and_never_sends_shares(settings, conn, src):
    from kairos.services.lists import add_ticker, set_shares, set_thesis

    add_ticker(conn, "holdings", "NVDA")
    set_shares(conn, "NVDA", 12.5)
    set_thesis(conn, "holdings", "NVDA", "AI data-center demand keeps growing")
    r = await build_reading(settings, conn, "NVDA", NOW)
    assert "AI data-center demand keeps growing" in src.last_prompt
    assert "12.5" not in src.last_prompt
    assert r.thesis_checked == "AI data-center demand keeps growing"
    assert r.ai.thesis_check.verdict == "challenges"


async def test_no_thesis_no_check(settings, conn, src):
    r = await build_reading(settings, conn, "NVDA", NOW)
    assert "Thesis to evaluate" not in src.last_prompt
    assert r.thesis_checked is None


async def test_thesis_recorded_even_when_ai_could_not_check(settings, conn, src):
    from kairos.services.lists import add_ticker, set_thesis

    add_ticker(conn, "holdings", "NVDA")
    set_thesis(conn, "holdings", "NVDA", "AI demand")
    src.finnhub_per_ticker, src.google_per_ticker = 1, 1  # too little news: no AI request
    r = await build_reading(settings, conn, "NVDA", NOW)
    assert r.ai is None
    assert r.thesis_checked == "AI demand"


async def test_reading_has_move_with_market(settings, conn, src):
    src.closes = {"NVDA": series(last=-9.3), "VOO": series(last=-4.4)}
    r = await build_reading(settings, conn, "NVDA", NOW)
    assert r.move.notable is True and r.move.market_share == "half"
    assert '"move"' in src.last_prompt


async def test_market_history_fetched_once_per_hour(settings, conn, src, monkeypatch):
    src.closes = {"VOO": series(last=-1.0)}
    calls = []

    async def counting(t, period="1y"):
        calls.append(t)
        return await src.get_history(t, period)

    monkeypatch.setattr(readings, "get_history", counting)
    await build_reading(settings, conn, "NVDA", NOW)
    await build_reading(settings, conn, "QQQ", NOW)
    assert calls.count("VOO") == 1


async def test_market_fetch_failure_omits_market_only(settings, conn, src):
    r = await build_reading(settings, conn, "NVDA", NOW)  # fakes have no VOO history
    assert r.move is not None and r.move.market_change_pct is None


async def test_second_reading_records_lean_change(settings, conn, src):
    await build_reading(settings, conn, "NVDA", NOW - timedelta(hours=12))
    src.lean = "neutral"
    r = await build_reading(settings, conn, "NVDA", NOW)
    (lean,) = [i for i in r.changes.items if i.kind == "lean"]
    assert (lean.before, lean.after) == ("bullish", "neutral")
