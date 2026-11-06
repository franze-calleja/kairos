from kairos.analysis.quick_numbers import build_quick_numbers, kind_from_info
from kairos.models import Holding

STOCK_INFO = {
    "quoteType": "EQUITY",
    "marketCap": 4.5e12,
    "trailingPE": 52.1,
    "forwardPE": 35.0,
    "sector": "Technology",
    "revenueGrowth": 0.62,
    "profitMargins": 0.55,
}


def test_kind_from_info():
    assert kind_from_info({"quoteType": "ETF"}) == "etf"
    assert kind_from_info(STOCK_INFO) == "stock"


def test_quick_numbers_stock():
    q = build_quick_numbers("stock", STOCK_INFO, [], {}, sector_pe=30.0)
    assert q.kind == "stock"
    assert q.market_cap == 4.5e12
    assert q.trailing_pe == 52.1
    assert q.forward_pe == 35.0
    assert q.sector == "Technology"
    assert q.sector_pe == 30.0
    assert q.revenue_growth == 0.62
    assert q.profit_margin == 0.55
    assert q.top_holdings == []


def test_quick_numbers_etf():
    holdings = [Holding(symbol="NVDA", name="NVIDIA", weight=0.09)]
    info = {"quoteType": "ETF", "totalAssets": 3.5e11, "netExpenseRatio": 0.2, "trailingPE": 33}
    q = build_quick_numbers("etf", info, holdings, {"expense_ratio": None, "aum": None}, None)
    assert q.kind == "etf"
    assert q.top_holdings == holdings
    assert q.aum == 3.5e11
    assert q.expense_ratio == 0.002  # info reports percent; stored as a fraction
    assert q.market_cap is None
    assert q.trailing_pe is None


def test_quick_numbers_etf_expense_prefers_fund_overview_aum_from_info():
    info = {"quoteType": "ETF", "totalAssets": 4.99e11}
    q = build_quick_numbers("etf", info, [], {"expense_ratio": 0.0003, "aum": 787282.2}, None)
    assert q.expense_ratio == 0.0003
    assert q.aum == 4.99e11  # fund_operations "Total Net Assets" uses other units; ignore it


def test_sector_pe_reference(tmp_path):
    from kairos.analysis.quick_numbers import sector_pe_reference

    p = tmp_path / "sector_pe.json"
    assert sector_pe_reference("Technology", p) is None
    p.write_text('{"generated": "2026-11-02", "sectors": {"Technology": 31.5}}')
    assert sector_pe_reference("Technology", p) == 31.5
    assert sector_pe_reference("Energy", p) is None
    assert sector_pe_reference(None, p) is None


def test_analyst_targets_for_stocks():
    info = {
        **STOCK_INFO,
        "targetMeanPrice": 327.14,
        "targetMedianPrice": 315.0,
        "targetLowPrice": 180.0,
        "targetHighPrice": 515.0,
        "numberOfAnalystOpinions": 58,
        "recommendationKey": "strong_buy",
    }
    q = build_quick_numbers("stock", info, [], {}, None)
    assert (q.target_mean, q.target_median, q.target_low, q.target_high) == (
        327.14,
        315.0,
        180.0,
        515.0,
    )
    assert q.analyst_count == 58
    assert q.analyst_rating == "Strong buy"


def test_no_analyst_targets_when_missing_or_etf():
    q = build_quick_numbers("stock", {**STOCK_INFO, "recommendationKey": "none"}, [], {}, None)
    assert q.target_mean is None and q.analyst_count is None and q.analyst_rating is None
    etf = build_quick_numbers("etf", {"quoteType": "ETF", "targetMeanPrice": 1.0}, [], {}, None)
    assert etf.target_mean is None
