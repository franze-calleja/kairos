"""True exposure: what the owner really holds once ETFs are looked through.

Local-only: share counts and values never leave the machine and never reach AI prompts.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from kairos.adapters.prices import get_info, get_sector_weightings, get_top_holdings

CACHE_FOR = timedelta(hours=6)
PRICE_MAX_AGE = timedelta(hours=24)
TOP_UNDERLYING = 15
SECTOR_NAMES = {
    "realestate": "Real Estate",
    "consumer_cyclical": "Consumer Cyclical",
    "basic_materials": "Basic Materials",
    "consumer_defensive": "Consumer Defensive",
    "technology": "Technology",
    "communication_services": "Communication Services",
    "financial_services": "Financial Services",
    "healthcare": "Healthcare",
    "industrials": "Industrials",
    "energy": "Energy",
    "utilities": "Utilities",
}
_cache: dict[tuple[str, str], tuple[datetime, Any]] = {}


async def _cached(kind: str, ticker: str, now: datetime, fetch) -> Any:
    hit = _cache.get((kind, ticker))
    if hit and hit[0] > now:
        return hit[1]
    value, _status = await fetch(ticker)
    _cache[(kind, ticker)] = (now + CACHE_FOR, value)
    return value


def _latest_payload(conn: sqlite3.Connection, ticker: str, now: datetime) -> dict | None:
    row = conn.execute(
        "SELECT created_at, payload FROM readings WHERE ticker = ? "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    if not row or now - datetime.fromisoformat(row["created_at"]) > PRICE_MAX_AGE:
        return None
    try:
        return json.loads(row["payload"])
    except ValueError:
        return None


async def _position(conn: sqlite3.Connection, ticker: str, now: datetime) -> dict | None:
    """Price, kind, name and (for stocks) sector for one holding; None if no price."""
    payload = _latest_payload(conn, ticker, now) or {}
    price = (payload.get("price") or {}).get("last_price")
    kind = payload.get("kind")
    name = payload.get("name")
    sector = (payload.get("quick") or {}).get("sector")
    if price is None or kind is None or (kind == "stock" and not sector):
        info, _ = await get_info(ticker)
        info = info or {}
        price = (
            price
            if price is not None
            else info.get("regularMarketPrice") or info.get("previousClose")
        )
        kind = kind or ("etf" if str(info.get("quoteType", "")).upper() == "ETF" else "stock")
        name = name or info.get("longName") or info.get("shortName")
        sector = sector or info.get("sector")
    if price is None:
        return None
    return {"price": float(price), "kind": kind, "name": name or ticker, "sector": sector}


async def compute_exposure(conn: sqlite3.Connection, now: datetime) -> dict:
    rows = conn.execute(
        "SELECT ticker, shares FROM lists "
        "WHERE list_name = 'holdings' AND shares IS NOT NULL ORDER BY ticker"
    ).fetchall()
    positions, missing = [], []
    for r in rows:
        info = await _position(conn, r["ticker"], now)
        if info is None:
            missing.append(r["ticker"])
            continue
        positions.append(
            {
                "ticker": r["ticker"],
                "shares": r["shares"],
                **info,
                "value": r["shares"] * info["price"],
            }
        )

    total = sum(p["value"] for p in positions)
    underlying: dict[str, dict] = {}
    sectors: dict[str, float] = {}
    rest = 0.0

    def add(symbol: str, name: str, value: float, via: str | None) -> None:
        u = underlying.setdefault(
            symbol, {"symbol": symbol, "name": name, "direct": 0.0, "via": {}}
        )
        if via:
            u["via"][via] = u["via"].get(via, 0.0) + value
        else:
            u["direct"] += value
            u["name"] = name

    for p in positions:
        if p["kind"] == "etf":
            holdings = await _cached("holdings", p["ticker"], now, get_top_holdings) or []
            for h in holdings:
                add(h.symbol, h.name, p["value"] * h.weight, p["ticker"])
            rest += p["value"] * max(0.0, 1 - sum(h.weight for h in holdings))
            weights = await _cached("sectors", p["ticker"], now, get_sector_weightings) or {}
            covered = 0.0
            for key, w in weights.items():
                label = SECTOR_NAMES.get(key, key.replace("_", " ").title())
                sectors[label] = sectors.get(label, 0.0) + p["value"] * w
                covered += w
            if covered < 0.999:
                sectors["Unknown"] = sectors.get("Unknown", 0.0) + p["value"] * (1 - covered)
        else:
            add(p["ticker"], p["name"], p["value"], None)
            label = p["sector"] or "Unknown"
            sectors[label] = sectors.get(label, 0.0) + p["value"]

    if not total:
        return {
            "total_value": 0,
            "positions": [],
            "underlying": [],
            "rest_of_funds": 0,
            "sectors": [],
            "missing_prices": missing,
        }

    def frac(v: float) -> float:
        return v / total

    out_underlying = sorted(
        (
            {
                "symbol": u["symbol"],
                "name": u["name"],
                "weight": frac(u["direct"] + sum(u["via"].values())),
                "direct": frac(u["direct"]),
                "via": {etf: frac(v) for etf, v in u["via"].items()},
            }
            for u in underlying.values()
        ),
        key=lambda u: -u["weight"],
    )[:TOP_UNDERLYING]
    return {
        "total_value": total,
        "positions": [
            {k: p[k] for k in ("ticker", "shares", "price", "value", "name", "kind")}
            | {"weight": frac(p["value"])}
            for p in sorted(positions, key=lambda p: -p["value"])
        ],
        "underlying": out_underlying,
        "rest_of_funds": frac(rest),
        "sectors": sorted(
            ({"sector": s, "weight": frac(v)} for s, v in sectors.items() if v > 0),
            key=lambda s: -s["weight"],
        ),
        "missing_prices": missing,
    }
