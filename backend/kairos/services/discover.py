"""Discover: tickers worth a look — unusual news spikes and funds/stocks similar to holdings."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from kairos.adapters.base import make_http_client
from kairos.adapters.finnhub import company_news
from kairos.adapters.prices import get_info, get_top_holdings
from kairos.config import Settings
from kairos.db import get_meta, set_meta
from kairos.services.lists import list_tickers

DATA = Path(__file__).parent.parent / "data"
UNIVERSE_PATH = DATA / "universe.txt"
ETF_LIST_PATH = DATA / "etf_list.txt"
SCAN_DAYS = 14
MIN_RECENT = 5
MIN_SPIKE_SCORE = 2.0  # recent news rate must be at least ~2x the ticker's usual rate
TOP_SPIKES = 10
MAX_SIMILAR_PER_HOLDING = 5
# Share classes of the same company in the S&P 500: owning one means the others aren't "new".
SHARE_CLASSES = [{"GOOG", "GOOGL"}, {"FOX", "FOXA"}, {"NWS", "NWSA"}, {"BRK-A", "BRK-B"}]


def _with_share_classes(tickers: set[str]) -> set[str]:
    out = set(tickers)
    for group in SHARE_CLASSES:
        if group & tickers:
            out |= group
    return out


def load_list(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def spike_score(daily_counts: list[int]) -> float:
    """daily_counts: SCAN_DAYS counts, oldest first. Recent 2-day rate vs prior 12-day rate."""
    recent = sum(daily_counts[-2:]) / 2
    baseline = sum(daily_counts[:-2]) / (len(daily_counts) - 2)
    return recent / (baseline + 0.5)


ProgressFn = Callable[[int, int], None]


async def _spikes(
    settings: Settings, owned: set[str], now: datetime, on_progress: ProgressFn | None = None
) -> list[dict]:
    today = now.date()
    found = []
    universe = load_list(UNIVERSE_PATH)
    async with make_http_client() as client:
        for i, ticker in enumerate(universe, 1):
            if on_progress:
                on_progress(i, len(universe))
            if ticker in owned:
                continue
            result = await company_news(client, settings, ticker, SCAN_DAYS, today=today)
            counts = [0] * SCAN_DAYS
            for item in result.items:
                age = (today - item.published_at.date()).days
                if 0 <= age < SCAN_DAYS:
                    counts[SCAN_DAYS - 1 - age] += 1
            recent = sum(counts[-2:])
            score = spike_score(counts)
            if recent >= MIN_RECENT and score >= MIN_SPIKE_SCORE:
                found.append(
                    {
                        "ticker": ticker,
                        "reason": f"news spike: {recent} articles in 2 days ({score:.1f}x usual)",
                        "score": score,
                    }
                )
    return sorted(found, key=lambda r: -r["score"])[:TOP_SPIKES]


async def _similar(owned: set[str], held: list[str]) -> list[dict]:
    etf_cache: dict[str, list] = {}

    async def holdings_of(etf: str) -> list:
        if etf not in etf_cache:
            etf_cache[etf], _ = await get_top_holdings(etf)
        return etf_cache[etf]

    out = []
    for ticker in held:
        info, _ = await get_info(ticker)
        suggestions = []
        if (info or {}).get("quoteType") == "ETF":
            for h in await holdings_of(ticker):
                if h.symbol not in owned:
                    suggestions.append(
                        {
                            "ticker": h.symbol,
                            "score": h.weight * 10,
                            "reason": f"top holding of {ticker} ({h.weight:.1%})",
                        }
                    )
        else:
            for etf in load_list(ETF_LIST_PATH):
                if etf in owned:
                    continue
                match = next((h for h in await holdings_of(etf) if h.symbol == ticker), None)
                if match:
                    suggestions.append(
                        {
                            "ticker": etf,
                            "score": match.weight * 10,
                            "reason": f"holds {ticker} ({match.weight:.1%})",
                        }
                    )
        suggestions.sort(key=lambda r: -r["score"])
        out += suggestions[:MAX_SIMILAR_PER_HOLDING]
    return out


async def run_discover(
    settings: Settings,
    conn: sqlite3.Connection,
    now: datetime,
    on_progress: ProgressFn | None = None,
) -> list[dict]:
    held = list_tickers(conn, "holdings")
    owned = _with_share_classes(set(held) | set(list_tickers(conn, "watching")))
    if settings.finnhub_api_key:
        spikes, scan = await _spikes(settings, owned, now, on_progress), "ok"
    else:
        spikes, scan = [], "not_configured"
    best: dict[str, dict] = {}
    for row in spikes + await _similar(owned, held):
        if row["ticker"] not in best:  # spikes first, then strongest similar
            best[row["ticker"]] = row
    items = list(best.values())
    created = now.astimezone(UTC).isoformat()
    conn.execute("DELETE FROM discover")
    conn.executemany(
        "INSERT INTO discover (created_at, ticker, reason, score) VALUES (?, ?, ?, ?)",
        [(created, r["ticker"], r["reason"], r["score"]) for r in items],
    )
    conn.commit()
    set_meta(conn, "discover_created_at", created)
    set_meta(conn, "discover_spike_scan", scan)
    return items


def latest_discover(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT ticker, reason, score FROM discover ORDER BY rowid").fetchall()
    return {
        "items": [dict(r) for r in rows],
        "created_at": get_meta(conn, "discover_created_at"),
        "spike_scan": get_meta(conn, "discover_spike_scan"),
    }
