from datetime import date
from typing import Any

import pandas as pd

from kairos.config import Settings
from kairos.models import HypeFlag, NewsItem

MAJOR_EXCHANGES = {"NMS", "NYQ", "NGM", "NCM", "ASE", "PCX", "BTS", "NAS", "NYS"}


def _money(value: float) -> str:
    for unit, size in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if value >= size:
            return (
                f"${value / size:.0f}{unit}"
                if value / size >= 100
                else f"${value / size:.1f}{unit}".replace(".0", "")
            )
    return f"${value:,.0f}"


def _attention(
    settings: Settings, news: list[NewsItem], substantive: bool | None, today: date
) -> HypeFlag:
    ages = [(today - n.published_at.date()).days for n in news]
    recent = sum(1 for a in ages if 0 <= a < 2)
    span = max(settings.news_window_days - 2, 1)
    baseline_daily = sum(1 for a in ages if 2 <= a < settings.news_window_days) / span
    spike = (
        recent >= settings.attention_min_articles
        and recent / 2 >= settings.attention_ratio * max(baseline_daily, 0.5)
    )
    value = f"{recent} articles in 2 days vs {baseline_daily:.1f}/day before"
    if substantive is None:
        return HypeFlag(
            code="attention_spike_no_substance",
            triggered=False,
            value=f"{value} (substance unknown)",
        )
    return HypeFlag(
        code="attention_spike_no_substance", triggered=spike and not substantive, value=value
    )


def compute_hype(
    settings: Settings,
    info: dict[str, Any],
    df: pd.DataFrame | None,
    news: list[NewsItem],
    substantive_news: bool | None,
    today: date,
) -> list[HypeFlag]:
    is_etf = str(info.get("quoteType", "")).upper() == "ETF"
    size = info.get("totalAssets") if is_etf else info.get("marketCap")
    size_label = "fund assets" if is_etf else "market cap"
    exchange = str(info.get("exchange") or "unknown")

    closes = df["Close"].astype(float).dropna() if df is not None and not df.empty else pd.Series()
    volumes = (
        df["Volume"].astype(float).dropna() if df is not None and not df.empty else pd.Series()
    )
    last = float(closes.iloc[-1]) if len(closes) else None
    spike_pct = (last / float(closes.iloc[-6]) - 1) * 100 if len(closes) >= 6 else None
    avg_vol = float(volumes.iloc[-30:].mean()) if len(volumes) else None

    if is_etf:
        attention = HypeFlag(
            code="attention_spike_no_substance", triggered=False, value="not applicable to ETFs"
        )
    else:
        attention = _attention(settings, news, substantive_news, today)
    return [
        attention,
        HypeFlag(
            code="micro_cap",
            triggered=size is not None and float(size) < settings.micro_cap_usd,
            value=f"{_money(float(size))} {size_label}"
            if size is not None
            else f"{size_label} unknown",
        ),
        HypeFlag(
            code="price_spike",
            triggered=spike_pct is not None and spike_pct > settings.price_spike_pct,
            value=f"{spike_pct:+.0f}% in 5 days"
            if spike_pct is not None
            else "not enough price data",
        ),
        HypeFlag(
            code="otc",
            triggered=exchange not in MAJOR_EXCHANGES and exchange != "unknown",
            value=f"exchange: {exchange}",
        ),
        HypeFlag(
            code="penny",
            triggered=last is not None and last < settings.penny_price,
            value=f"${last:,.2f} share price" if last is not None else "price unknown",
        ),
        HypeFlag(
            code="low_volume",
            triggered=avg_vol is not None and avg_vol < settings.low_volume,
            value=f"{avg_vol:,.0f} avg daily volume" if avg_vol is not None else "volume unknown",
        ),
    ]
