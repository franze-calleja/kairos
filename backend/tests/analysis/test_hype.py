from datetime import UTC, date, datetime, timedelta

from kairos.analysis.hype import compute_hype
from kairos.models import NewsItem
from tests.helpers import make_df

TODAY = date(2026, 11, 2)
ORDER = ["attention_spike_no_substance", "micro_cap", "price_spike", "otc", "penny", "low_volume"]
NVDA_INFO = {"quoteType": "EQUITY", "marketCap": 4.5e12, "exchange": "NMS"}


def news(days_ago: list[int]) -> list[NewsItem]:
    now = datetime(2026, 11, 2, 12, tzinfo=UTC)
    return [
        NewsItem(
            id=f"n{i}",
            source="finnhub",
            title=f"t{i}",
            summary="",
            url=f"https://e/{i}",
            published_at=now - timedelta(days=d),
            related_ticker="X",
        )
        for i, d in enumerate(days_ago)
    ]


def triggered(flags):
    return {f.code for f in flags if f.triggered}


def test_megacap_no_flags(settings):
    flags = compute_hype(
        settings, NVDA_INFO, make_df([180.0] * 60, volume=2e8), news([1, 3]), True, TODAY
    )
    assert [f.code for f in flags] == ORDER
    assert triggered(flags) == set()


def test_pump_profile(settings):
    info = {"quoteType": "EQUITY", "marketCap": 2e8, "exchange": "PNK"}
    closes = [0.85] * 55 + [0.9, 0.95, 1.0, 1.1, 1.2]
    flags = compute_hype(settings, info, make_df(closes, volume=50_000), [], None, TODAY)
    assert triggered(flags) == {"micro_cap", "price_spike", "otc", "penny", "low_volume"}
    by_code = {f.code: f for f in flags}
    assert by_code["otc"].value == "exchange: PNK"
    assert by_code["micro_cap"].value == "$200M market cap"
    assert by_code["price_spike"].value.startswith("+41%")


def test_attention_spike_requires_no_substance(settings):
    items = news([0, 0, 0, 1, 1, 1, 1, 1, 3, 5])  # 8 in last 2 days, 2 in prior 5
    df = make_df([180.0] * 60, volume=2e8)
    assert "attention_spike_no_substance" in triggered(
        compute_hype(settings, NVDA_INFO, df, items, False, TODAY)
    )
    assert "attention_spike_no_substance" not in triggered(
        compute_hype(settings, NVDA_INFO, df, items, True, TODAY)
    )
    unknown = compute_hype(settings, NVDA_INFO, df, items, None, TODAY)
    flag = next(f for f in unknown if f.code == "attention_spike_no_substance")
    assert not flag.triggered
    assert "substance unknown" in flag.value


def test_attention_min_articles(settings):
    df = make_df([180.0] * 60, volume=2e8)
    flags = compute_hype(settings, NVDA_INFO, df, news([0, 0, 1, 1]), False, TODAY)
    assert "attention_spike_no_substance" not in triggered(flags)


def test_etf_micro_cap_uses_total_assets(settings):
    info = {"quoteType": "ETF", "totalAssets": 5e7, "exchange": "PCX"}
    flags = compute_hype(settings, info, make_df([50.0] * 60, volume=1e6), [], True, TODAY)
    assert triggered(flags) == {"micro_cap"}


def test_no_price_data_does_not_crash(settings):
    flags = compute_hype(settings, NVDA_INFO, None, [], True, TODAY)
    assert [f.code for f in flags] == ORDER
    assert triggered(flags) == set()
