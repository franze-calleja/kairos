"""Fake data sources for reading orchestration tests."""

from datetime import UTC, datetime, timedelta

from kairos.adapters.base import error, not_configured, ok
from kairos.ai.schema import AISummary, Claim, ThesisCheck
from kairos.models import AdapterResult, Holding, NewsItem
from tests.helpers import make_df

NOW = datetime(2026, 11, 2, 3, 0, tzinfo=UTC)
STOCK_INFO = {
    "quoteType": "EQUITY",
    "longName": "NVIDIA Corporation",
    "marketCap": 4.5e12,
    "exchange": "NMS",
    "sector": "Technology",
    "trailingPE": 50.0,
    "previousClose": 180.0,
}
ETF_INFO = {
    "quoteType": "ETF",
    "longName": "Invesco QQQ Trust",
    "totalAssets": 3.5e11,
    "exchange": "NMS",
    "netExpenseRatio": 0.2,
    "previousClose": 600.0,
}


def make_news(ticker, n, source="finnhub", prefix=None):
    prefix = prefix or ticker
    return [
        NewsItem(
            id=f"{prefix}-{source}-{i}",
            source=source,
            title=f"{prefix} {source} story {i}",
            summary="details",
            url=f"https://e/{prefix}/{source}/{i}",
            published_at=NOW - timedelta(hours=i),
            related_ticker=ticker,
        )
        for i in range(n)
    ]


class Sources:
    def __init__(self):
        self.info = {"NVDA": STOCK_INFO, "QQQ": ETF_INFO}
        self.holdings = {
            "QQQ": [
                Holding(symbol=s, name=s, weight=w)
                for s, w in [
                    ("NVDA", 0.09),
                    ("MSFT", 0.08),
                    ("AAPL", 0.07),
                    ("AMZN", 0.05),
                    ("AVGO", 0.05),
                    ("META", 0.04),
                    ("GOOGL", 0.03),
                    ("GOOG", 0.03),
                    ("TSLA", 0.03),
                    ("COST", 0.02),
                ]
            ]
        }
        self.finnhub_per_ticker = 3
        self.google_per_ticker = 2
        self.finnhub_status = "ok"
        self.summary_status = "ok"
        self.summarize_calls = 0
        self.calls = 0
        self.news_tickers = []
        self.closes: dict[str, list[float]] = {}
        self.move_reason: Claim | None = None

    async def get_info(self, t):
        self.calls += 1
        if t in self.info:
            return self.info[t], ok("yfinance")
        return None, error("yfinance", "unknown ticker")

    async def get_history(self, t, period="1y"):
        if t in self.info or t in self.closes:
            return make_df(self.closes.get(t, [100.0] * 260)), ok("yfinance")
        return None, error("yfinance", "no price history")

    async def get_top_holdings(self, t):
        h = self.holdings.get(t, [])
        return h, ok("yfinance") if h else error("yfinance", "no holdings data")

    async def get_fund_overview(self, t):
        return {"expense_ratio": 0.002, "aum": 3.5e11}, ok("yfinance")

    async def company_news(self, client, settings, t, days, today=None):
        self.news_tickers.append(t)
        if self.finnhub_status == "not_configured":
            return AdapterResult[NewsItem](items=[], status=not_configured("finnhub"))
        return AdapterResult[NewsItem](
            items=make_news(t, self.finnhub_per_ticker), status=ok("finnhub")
        )

    async def earnings_calendar(self, client, settings, t, days_ahead=90, today=None):
        self.earnings_today = today
        return getattr(self, "next_earnings", None), ok("finnhub")

    async def google_search(self, client, query, related, days):
        return AdapterResult[NewsItem](
            items=make_news(related, self.google_per_ticker, "google_news"),
            status=ok("google_news"),
        )

    async def recent_filings(self, client, settings, t, days, today=None):
        return AdapterResult[NewsItem](items=[], status=not_configured("sec"))

    async def reddit_mentions(self, client, settings, t, days):
        from kairos.adapters.base import disabled

        return AdapterResult[NewsItem](items=[], status=disabled("reddit"))

    async def summarize(self, settings, budget, prompt, allowed_ids, now):
        self.summarize_calls += 1
        self.last_prompt = prompt
        if self.summary_status != "ok":
            return None, self.summary_status
        sid = sorted(allowed_ids)[0]
        thesis_check = None
        if "Thesis to evaluate" in prompt:
            thesis_check = ThesisCheck(
                verdict="challenges", text="News cuts against it", source_ids=[sid]
            )
        return AISummary(
            thesis_check=thesis_check,
            move_reason=self.move_reason,
            lean="bullish",
            confidence="medium",
            not_enough_signal=False,
            substantive_news=True,
            drivers=[Claim(text="Driver", source_ids=[sid])],
            bull_case=[Claim(text="Bull", source_ids=[sid])],
            bear_case=[Claim(text="Bear", source_ids=[sid])],
        ), "ok"

    def install(self, monkeypatch):
        from kairos.services import readings

        for name in (
            "get_info",
            "get_history",
            "get_top_holdings",
            "get_fund_overview",
            "company_news",
            "earnings_calendar",
            "google_search",
            "recent_filings",
            "reddit_mentions",
            "summarize",
        ):
            monkeypatch.setattr(readings, name, getattr(self, name))
        return self
