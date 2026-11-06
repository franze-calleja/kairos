from datetime import timedelta

import pytest

from kairos.ai.schema import ThesisCheck
from kairos.analysis.changes import compute_changes
from kairos.models import HypeFlag
from kairos.services.readings import build_reading
from tests.services.fakes import NOW, Sources


@pytest.fixture
async def base(settings, conn, monkeypatch):
    Sources().install(monkeypatch)
    return await build_reading(settings, conn, "NVDA", NOW)


def at(r, hours_ago):
    return r.model_copy(update={"created_at": NOW - timedelta(hours=hours_ago)})


def with_lean(r, lean):
    return r.model_copy(update={"ai": r.ai.model_copy(update={"lean": lean})})


def with_verdict(r, verdict, thesis="AI demand"):
    check = ThesisCheck(verdict=verdict, text="x", source_ids=[])
    return r.model_copy(
        update={"thesis_checked": thesis, "ai": r.ai.model_copy(update={"thesis_check": check})}
    )


def items(ch, kind):
    return [i for i in ch.items if i.kind == kind]


async def test_first_reading_has_no_changes(base):
    assert compute_changes(base, None, None) is None


async def test_lean_change_against_last_ok_ai_reading(base):
    prev_ai = at(with_lean(base, "bullish"), 48)
    prev = at(base, 1).model_copy(update={"ai": None, "ai_status": "budget_exhausted"})
    cur = with_lean(base, "neutral")
    ch = compute_changes(cur, prev, prev_ai)
    assert ch.since == prev.created_at
    (lean,) = items(ch, "lean")
    assert (lean.before, lean.after, lean.since) == ("bullish", "neutral", prev_ai.created_at)


async def test_verdict_change_only_when_same_reason_text(base):
    prev = at(with_verdict(base, "supports"), 12)
    (v,) = items(compute_changes(with_verdict(base, "mixed"), prev, prev), "verdict")
    assert (v.before, v.after) == ("supports", "mixed")
    other = with_verdict(base, "mixed", thesis="Different reason")
    assert items(compute_changes(other, prev, prev), "verdict") == []


async def test_computed_changes_vs_immediately_previous(base):
    prev = at(base, 12)
    prev = prev.model_copy(
        update={
            "price": prev.price.model_copy(update={"label": "near_average"}),
            "quick": prev.quick.model_copy(update={"target_mean": 327.14}),
            "sources": prev.sources[2:],
        }
    )
    hype = [HypeFlag(code="price_spike", triggered=True, value="+40%")]
    cur = base.model_copy(
        update={
            "price": base.price.model_copy(update={"label": "below_range"}),
            "quick": base.quick.model_copy(update={"target_mean": 310.0}),
            "hype": hype,
        }
    )
    ch = compute_changes(cur, prev, prev)
    (label,) = items(ch, "price_label")
    assert (label.before, label.after) == ("near_average", "below_range")
    (h,) = items(ch, "hype")
    assert (h.before, h.after) == ("clear", "warning")
    (t,) = items(ch, "target")
    assert (t.before, t.after) == ("327.14", "310.00")
    (n,) = items(ch, "new_articles")
    assert n.count == 2
    small = cur.model_copy(update={"quick": cur.quick.model_copy(update={"target_mean": 330.0})})
    small_prev = prev.model_copy(
        update={"quick": prev.quick.model_copy(update={"target_mean": 327.0})}
    )
    assert items(compute_changes(small, small_prev, small_prev), "target") == []


async def test_no_items_returns_empty_list_not_none(base):
    prev = at(base, 12)
    ch = compute_changes(base, prev, prev)
    assert ch is not None and ch.items == []
