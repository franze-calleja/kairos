"""Builds a Reading for one ticker: collect -> clean -> compute -> summarize -> store."""

import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from kairos.adapters.base import disabled, error, make_http_client, ok
from kairos.adapters.finnhub import company_news, earnings_calendar
from kairos.adapters.google_news import search as google_search
from kairos.adapters.prices import get_fund_overview, get_history, get_info, get_top_holdings
from kairos.adapters.reddit import mentions as reddit_mentions
from kairos.adapters.sec import recent_filings
from kairos.ai.budget import RequestBudget
from kairos.ai.gemini import summarize
from kairos.ai.prompt import build_prompt
from kairos.analysis.clean import clean_news
from kairos.analysis.events import build_events, ex_dividend_from_info, load_macro
from kairos.analysis.hype import compute_hype
from kairos.analysis.price_context import compute_price_context
from kairos.analysis.quick_numbers import build_quick_numbers, kind_from_info, sector_pe_reference
from kairos.config import Settings
from kairos.models import AdapterResult, NewsItem, Reading, SourceStatus
from kairos.tickers import normalize_ticker

MIN_NEWS_FOR_AI = 3
ETF_HOLDINGS = 10
ETF_NEWS_SLOTS = 30
MARKET_NEWS_MAX = 10
MARKET_NEWS_WEIGHT = 0.05
_SEVERITY = {"error": 3, "not_configured": 2, "disabled": 1, "ok": 0}


class UnknownTicker(Exception):
    pass


class DataUnavailable(Exception):
    pass


def _merge_health(statuses: list[SourceStatus]) -> list[SourceStatus]:
    worst: dict[str, SourceStatus] = {}
    for s in statuses:
        current = worst.get(s.name)
        if current is None or _SEVERITY[s.status] > _SEVERITY[current.status]:
            worst[s.name] = s
    return list(worst.values())


async def _ticker_news(client, settings: Settings, ticker: str, name: str, days: int):
    query = f'"{ticker}" OR "{name}" stock' if name and name != ticker else f'"{ticker}" stock'
    results: list[AdapterResult[NewsItem]] = await asyncio.gather(
        company_news(client, settings, ticker, days),
        google_search(client, query, ticker, days),
        recent_filings(client, settings, ticker, days),
        reddit_mentions(client, settings, ticker, days),
    )
    return [i for r in results for i in r.items], [r.status for r in results]


async def _holding_news(client, settings: Settings, symbol: str, name: str, days: int):
    results = await asyncio.gather(
        company_news(client, settings, symbol, days),
        google_search(client, f'"{symbol}" OR "{name}" stock', symbol, days),
    )
    return [i for r in results for i in r.items], [r.status for r in results]


async def _etf_news(client, settings: Settings, ticker: str, name: str, holdings, days: int):
    top = holdings[:ETF_HOLDINGS]
    total = sum(h.weight for h in top) or 1.0
    per_holding = await asyncio.gather(
        *(_holding_news(client, settings, h.symbol, h.name, days) for h in top)
    )
    items: list[NewsItem] = []
    statuses: list[SourceStatus] = []
    for h, (news, sts) in zip(top, per_holding, strict=True):
        allot = max(1, round(h.weight / total * ETF_NEWS_SLOTS))
        news = sorted(news, key=lambda n: n.published_at, reverse=True)[:allot]
        items += [n.model_copy(update={"weight": h.weight}) for n in news]
        statuses += sts
    market = await google_search(client, "stock market", "MARKET", days)
    items += [
        n.model_copy(update={"weight": MARKET_NEWS_WEIGHT}) for n in market.items[:MARKET_NEWS_MAX]
    ]
    statuses.append(market.status)
    return items, statuses


def _computed_for_prompt(reading_parts: dict[str, Any]) -> dict[str, Any]:
    price = reading_parts["price"]
    return {
        "price": price.model_dump(exclude={"history"}) if price else None,
        "events": reading_parts["events"].model_dump(),
        "quick_numbers": reading_parts["quick"].model_dump(),
        "hype_flags": [f.model_dump() for f in reading_parts["hype"] if f.triggered],
    }


async def build_reading(
    settings: Settings, conn: sqlite3.Connection, ticker: str, now: datetime
) -> Reading:
    symbol = normalize_ticker(ticker)
    (info, info_status), (df, hist_status) = await asyncio.gather(
        get_info(symbol), get_history(symbol)
    )
    if info is None and df is None:
        if info_status.detail == "unknown ticker":
            raise UnknownTicker(symbol)
        raise DataUnavailable(info_status.detail or "market data unavailable")
    info = info or {}
    statuses = [info_status, hist_status]
    kind = kind_from_info(info)
    name = info.get("longName") or info.get("shortName") or symbol
    days = settings.news_window_days
    today = now.astimezone(ZoneInfo(settings.tz)).date()  # the user's calendar day

    async with make_http_client() as client:
        holdings, fund = [], {"expense_ratio": None, "aum": None}
        if kind == "etf":
            (holdings, h_status), (fund, f_status) = await asyncio.gather(
                get_top_holdings(symbol), get_fund_overview(symbol)
            )
            statuses += [h_status, f_status]
        if holdings:
            raw, news_statuses = await _etf_news(client, settings, symbol, name, holdings, days)
        else:
            raw, news_statuses = await _ticker_news(client, settings, symbol, name, days)
        statuses += news_statuses
        next_earnings = None
        if kind == "stock":
            next_earnings, e_status = await earnings_calendar(client, settings, symbol, today=today)
            statuses.append(e_status)

    cleaned = clean_news(raw)
    # Hype attention needs the full deduplicated stream, not the capped list sent to the AI.
    deduped = clean_news(raw, max_items=max(len(raw), 1))
    parts: dict[str, Any] = {
        "price": compute_price_context(df) if df is not None else None,
        "events": build_events(today, next_earnings, ex_dividend_from_info(info), load_macro()),
        "quick": build_quick_numbers(
            kind, info, holdings, fund, sector_pe_reference(info.get("sector"))
        ),
        "hype": compute_hype(settings, info, df, deduped, None, today),
    }

    ai, ai_status = None, "not_enough_signal"
    if len(cleaned) < MIN_NEWS_FOR_AI:
        statuses.append(
            disabled("gemini").model_copy(update={"detail": "skipped: too little news"})
        )
    else:
        budget = RequestBudget(conn, settings.gemini_rpm, settings.gemini_rpd, settings.tz)
        prompt = build_prompt(symbol, name, kind, cleaned, _computed_for_prompt(parts))
        ai, gemini_status = await summarize(settings, budget, prompt, {n.id for n in cleaned}, now)
        if gemini_status == "ok":
            ai_status = "not_enough_signal" if ai and ai.not_enough_signal else "ok"
            statuses.append(ok("gemini"))
        elif gemini_status == "not_configured":
            ai_status = "not_configured"
            statuses.append(SourceStatus(name="gemini", status="not_configured"))
        else:
            ai_status = gemini_status
            statuses.append(error("gemini", gemini_status.replace("_", " ")))
        parts["hype"] = compute_hype(
            settings, info, df, deduped, ai.substantive_news if ai else None, today
        )

    reading = Reading(
        ticker=symbol,
        name=name,
        kind=kind,
        created_at=now,
        ai=ai,
        ai_status=ai_status,
        sources=cleaned,
        data_health=_merge_health(statuses),
        **parts,
    )
    conn.execute(
        "INSERT INTO readings (ticker, created_at, lean, confidence, ai_status, price_at, payload)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            symbol,
            now.isoformat(),
            ai.lean if ai and ai_status == "ok" else None,
            ai.confidence if ai and ai_status == "ok" else None,
            ai_status,
            reading.price.last_price if reading.price else None,
            reading.model_dump_json(),
        ),
    )
    conn.commit()
    return reading


def latest_reading(conn: sqlite3.Connection, ticker: str) -> Reading | None:
    row = conn.execute(
        "SELECT payload FROM readings WHERE ticker = ? ORDER BY created_at DESC, id DESC LIMIT 1",
        (normalize_ticker(ticker),),
    ).fetchone()
    return Reading.model_validate_json(row["payload"]) if row else None


async def get_reading(
    settings: Settings,
    conn: sqlite3.Connection,
    ticker: str,
    now: datetime,
    refresh: bool = False,
) -> Reading:
    if not refresh:
        cached = latest_reading(conn, ticker)
        if cached and now - cached.created_at < timedelta(hours=settings.reading_cache_hours):
            return cached
    return await build_reading(settings, conn, ticker, now)
