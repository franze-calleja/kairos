from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from kairos.ai.schema import AISummary

SourceName = Literal["yfinance", "finnhub", "google_news", "sec", "reddit", "gemini"]
AIStatus = Literal["ok", "not_enough_signal", "budget_exhausted", "unavailable", "not_configured"]


class SourceStatus(BaseModel):
    name: SourceName
    status: Literal["ok", "error", "disabled", "not_configured"]
    detail: str | None = None


class NewsItem(BaseModel):
    id: str
    source: SourceName
    title: str
    summary: str
    url: str
    published_at: datetime
    related_ticker: str
    weight: float = 1.0
    outlet: str | None = None  # publisher shown to the user, e.g. "Reuters"


class AdapterResult[T](BaseModel):
    items: list[T]
    status: SourceStatus


class PricePoint(BaseModel):
    date: date
    close: float


class PriceContext(BaseModel):
    last_price: float
    day_change_pct: float | None
    ma50: float | None
    ma200: float | None
    pct_vs_ma50: float | None
    pct_vs_ma200: float | None
    high_52w: float
    low_52w: float
    pct_from_52w_high: float
    volatility_30d: float | None
    label: Literal["stretched", "near_average", "below_range", "insufficient_history"]
    history: list[PricePoint]


class Move(BaseModel):
    """The last completed trading day's move, in context. All numbers computed, never AI."""

    date: date
    change_pct: float
    typical_pct: float | None  # the ticker's normal daily swing before this day
    notable: bool
    biggest_since: date | None = None  # notable only; None = biggest in the history window
    market_open: bool = False  # an in-progress session was excluded
    history_start: date | None = None  # first completed close we have (short for new listings)
    market_change_pct: float | None = None  # S&P 500 (VOO) on the same date
    market_notable: bool | None = None
    market_share: Literal["market", "half", "ticker", "opposite"] | None = None


class ChangeItem(BaseModel):
    """One thing that differs from an earlier reading of the same ticker."""

    kind: Literal["lean", "verdict", "price_label", "hype", "target", "new_articles"]
    before: str | None = None
    after: str | None = None
    count: int | None = None  # new_articles only
    since: datetime  # the reading this item compares against


class Changes(BaseModel):
    since: datetime  # the immediately previous reading
    items: list[ChangeItem]


class MacroEvent(BaseModel):
    date: date
    kind: Literal["FOMC", "CPI"]


class Events(BaseModel):
    next_earnings: date | None
    earnings_within_7d: bool
    next_ex_dividend: date | None
    macro: list[MacroEvent]


class Holding(BaseModel):
    symbol: str
    name: str
    weight: float


class QuickNumbers(BaseModel):
    kind: Literal["stock", "etf"]
    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    sector: str | None = None
    sector_pe: float | None = None
    revenue_growth: float | None = None
    profit_margin: float | None = None
    expense_ratio: float | None = None
    aum: float | None = None
    top_holdings: list[Holding] = []
    # Analysts' 12-month price targets (stocks only; other people's opinion, shown as such)
    target_mean: float | None = None
    target_median: float | None = None
    target_low: float | None = None
    target_high: float | None = None
    analyst_count: int | None = None
    analyst_rating: str | None = None


class HypeFlag(BaseModel):
    code: Literal[
        "attention_spike_no_substance", "micro_cap", "price_spike", "otc", "penny", "low_volume"
    ]
    triggered: bool
    value: str


class Reading(BaseModel):
    ticker: str
    name: str
    kind: Literal["stock", "etf"]
    created_at: datetime
    price: PriceContext | None
    events: Events
    quick: QuickNumbers
    hype: list[HypeFlag]
    ai: AISummary | None
    ai_status: AIStatus
    sources: list[NewsItem]
    data_health: list[SourceStatus]
    thesis_checked: str | None = None  # the owner's reason this reading evaluated, if any
    move: Move | None = None
    changes: Changes | None = None
