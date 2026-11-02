import asyncio
from typing import Any

import pandas as pd
import yfinance as yf

from kairos.adapters.base import error, ok
from kairos.models import Holding, SourceStatus


def _history(ticker: str, period: str) -> pd.DataFrame:
    return yf.Ticker(ticker).history(period=period, auto_adjust=True)


async def get_history(ticker: str, period: str = "1y") -> tuple[pd.DataFrame | None, SourceStatus]:
    try:
        df = await asyncio.to_thread(_history, ticker, period)
    except Exception as e:  # yfinance raises many types; treat all as source errors
        return None, error("yfinance", f"history: {e}")
    if df is None or df.empty:
        return None, error("yfinance", "no price history")
    return df[["Close", "Volume"]].dropna(subset=["Close"]), ok("yfinance")


async def get_info(ticker: str) -> tuple[dict[str, Any] | None, SourceStatus]:
    try:
        info = await asyncio.to_thread(lambda: dict(yf.Ticker(ticker).info or {}))
    except Exception as e:
        return None, error("yfinance", f"info: {e}")
    has_price = any(info.get(k) is not None for k in ("regularMarketPrice", "previousClose"))
    if not info.get("quoteType") and not has_price:
        return None, error("yfinance", "unknown ticker")
    return info, ok("yfinance")


def _top_holdings(etf: str) -> list[Holding]:
    df = yf.Ticker(etf).funds_data.top_holdings
    if df is None or df.empty:
        return []
    return [
        Holding(symbol=str(sym), name=str(row.get("Name", sym)), weight=float(row["Holding Percent"]))
        for sym, row in df.iterrows()
    ]


async def get_top_holdings(etf: str) -> tuple[list[Holding], SourceStatus]:
    try:
        holdings = await asyncio.to_thread(_top_holdings, etf)
    except Exception as e:
        return [], error("yfinance", f"holdings: {e}")
    if not holdings:
        return [], error("yfinance", "no holdings data")
    return holdings, ok("yfinance")


def _fund_overview(etf: str) -> dict[str, float | None]:
    ops = yf.Ticker(etf).funds_data.fund_operations
    out: dict[str, float | None] = {"expense_ratio": None, "aum": None}
    if ops is not None and not ops.empty:
        col = ops.columns[0]
        for label, key in (("Annual Report Expense Ratio", "expense_ratio"), ("Total Net Assets", "aum")):
            if label in ops.index:
                value = ops.loc[label, col]
                out[key] = float(value) if pd.notna(value) else None
    return out


async def get_fund_overview(etf: str) -> tuple[dict[str, float | None], SourceStatus]:
    try:
        return await asyncio.to_thread(_fund_overview, etf), ok("yfinance")
    except Exception as e:
        return {"expense_ratio": None, "aum": None}, error("yfinance", f"fund overview: {e}")
