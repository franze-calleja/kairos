"""What changed since the last reading of the same ticker. Computed, never AI."""

from kairos.models import ChangeItem, Changes, Reading

TARGET_CHANGE_PCT = 5.0


def _ai_items(current: Reading, previous_ai: Reading | None) -> list[ChangeItem]:
    """Lean/verdict changes; only between two readings that both had a real AI read."""
    if (
        current.ai is None
        or current.ai_status != "ok"
        or previous_ai is None
        or previous_ai.ai is None
        or previous_ai.ai_status != "ok"
    ):
        return []
    since = previous_ai.created_at
    out: list[ChangeItem] = []
    if current.ai.lean != previous_ai.ai.lean:
        out.append(
            ChangeItem(kind="lean", before=previous_ai.ai.lean, after=current.ai.lean, since=since)
        )
    before, after = previous_ai.ai.thesis_check, current.ai.thesis_check
    same_reason = current.thesis_checked and current.thesis_checked == previous_ai.thesis_checked
    if same_reason and before and after and before.verdict != after.verdict:
        out.append(
            ChangeItem(kind="verdict", before=before.verdict, after=after.verdict, since=since)
        )
    return out


def _computed_items(current: Reading, previous: Reading) -> list[ChangeItem]:
    since = previous.created_at
    out: list[ChangeItem] = []
    if current.price and previous.price and current.price.label != previous.price.label:
        out.append(
            ChangeItem(
                kind="price_label",
                before=previous.price.label,
                after=current.price.label,
                since=since,
            )
        )
    was = any(f.triggered for f in previous.hype)
    now = any(f.triggered for f in current.hype)
    if was != now:
        out.append(
            ChangeItem(
                kind="hype",
                before="warning" if was else "clear",
                after="warning" if now else "clear",
                since=since,
            )
        )
    old_t, new_t = previous.quick.target_mean, current.quick.target_mean
    if old_t and new_t and abs(new_t / old_t - 1) * 100 >= TARGET_CHANGE_PCT:
        out.append(
            ChangeItem(kind="target", before=f"{old_t:.2f}", after=f"{new_t:.2f}", since=since)
        )
    seen = {n.id for n in previous.sources}
    new = sum(1 for n in current.sources if n.id not in seen)
    if new:
        out.append(ChangeItem(kind="new_articles", count=new, since=since))
    return out


def compute_changes(
    current: Reading, previous: Reading | None, previous_ai: Reading | None
) -> Changes | None:
    if previous is None:
        return None
    items = _ai_items(current, previous_ai) + _computed_items(current, previous)
    return Changes(since=previous.created_at, items=items)
