import pandas as pd

from kairos.adapters import prices


class FakeFunds:
    top_holdings = pd.DataFrame(
        {"Name": ["NVIDIA Corp", "Microsoft Corp"], "Holding Percent": [0.09, 0.08]},
        index=pd.Index(["NVDA", "MSFT"], name="Symbol"),
    )
    fund_operations = pd.DataFrame()


class FakeTicker:
    def __init__(self, symbol, info=None, history=None):
        self.info = info or {}
        self._history = history if history is not None else pd.DataFrame()
        self.funds_data = FakeFunds()

    def history(self, period="1y", **kwargs):
        return self._history


async def test_top_holdings_mapping(monkeypatch):
    monkeypatch.setattr(prices.yf, "Ticker", lambda s: FakeTicker(s))
    holdings, status = await prices.get_top_holdings("QQQ")
    assert status.status == "ok"
    assert [(h.symbol, h.name, h.weight) for h in holdings] == [
        ("NVDA", "NVIDIA Corp", 0.09),
        ("MSFT", "Microsoft Corp", 0.08),
    ]


async def test_unknown_ticker_status(monkeypatch):
    monkeypatch.setattr(prices.yf, "Ticker", lambda s: FakeTicker(s, info={"trailingPegRatio": None}))
    info, status = await prices.get_info("XYZQQ")
    assert info is None
    assert status.status == "error"
    assert status.detail == "unknown ticker"


async def test_known_ticker_info(monkeypatch):
    monkeypatch.setattr(
        prices.yf, "Ticker", lambda s: FakeTicker(s, info={"quoteType": "EQUITY", "previousClose": 1.0})
    )
    info, status = await prices.get_info("NVDA")
    assert status.status == "ok"
    assert info["quoteType"] == "EQUITY"


async def test_history_exception_is_error(monkeypatch):
    def boom(s):
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(prices.yf, "Ticker", boom)
    df, status = await prices.get_history("NVDA")
    assert df is None
    assert status.status == "error"
