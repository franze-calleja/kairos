from datetime import UTC, datetime, timedelta

from kairos.analysis.clean import clean_news
from kairos.models import NewsItem

T0 = datetime(2026, 11, 1, tzinfo=UTC)


def item(i, title, summary="s", weight=1.0, url=None):
    return NewsItem(
        id=f"id{i}",
        source="finnhub",
        title=title,
        summary=summary,
        url=url or f"https://example.com/{i}",
        published_at=T0 - timedelta(hours=i),
        related_ticker="NVDA",
        weight=weight,
    )


def test_clean_dedupes_by_title():
    out = clean_news([item(1, "NVDA beats!"), item(2, "nvda beats"), item(3, "Other")])
    assert [i.title for i in out] == ["NVDA beats!", "Other"]


def test_clean_dedupes_by_id():
    a = item(1, "A")
    assert len(clean_news([a, a.model_copy(update={"title": "A different"})])) == 1


def test_clean_caps_items():
    assert len(clean_news([item(i, f"title {i}") for i in range(50)])) == 40


def test_clean_trims_and_strips_html():
    out = clean_news([item(1, "A", summary="<b>x</b>" + "y" * 500), item(2, "", summary="z")])
    assert len(out) == 1
    assert out[0].summary.startswith("x y")
    assert "<b>" not in out[0].summary
    assert len(out[0].summary) == 400


def test_clean_plain_tag_strip():
    assert clean_news([item(1, "A", summary="<b>x</b>")])[0].summary == "x"


def test_clean_sorts_weight_then_recency():
    out = clean_news(
        [item(1, "new low", weight=0.1), item(5, "old high", weight=0.9), item(2, "b")]
    )
    assert [i.title for i in out] == ["b", "old high", "new low"]
