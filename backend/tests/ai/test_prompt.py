import inspect
from datetime import UTC, datetime

from kairos.ai.prompt import build_prompt
from kairos.models import NewsItem


def test_prompt_has_ids_and_rules():
    item = NewsItem(
        id="abc1234567",
        source="finnhub",
        title="Nvidia raises guidance",
        summary="Strong AI demand",
        url="https://e/1",
        published_at=datetime(2026, 11, 1, tzinfo=UTC),
        related_ticker="NVDA",
        weight=0.09,
    )
    prompt = build_prompt("NVDA", "NVIDIA Corp", "stock", [item], {"price": {"last_price": 180.0}})
    assert "[abc1234567]" in prompt
    assert "(finnhub, 2026-11-01, 0.09)" in prompt
    assert "only the listed articles" in prompt
    assert "not_enough_signal" in prompt
    assert "takeaway" in prompt
    assert "180.0" in prompt


def test_prompt_signature_has_no_portfolio_inputs():
    params = " ".join(inspect.signature(build_prompt).parameters).lower()
    for word in ("holding", "watch", "quantity", "portfolio"):
        assert word not in params
