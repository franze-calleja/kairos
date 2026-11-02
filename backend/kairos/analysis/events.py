import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from kairos.models import Events, MacroEvent

MACRO_PATH = Path(__file__).parent.parent / "data" / "macro_calendar.json"


def load_macro(path: Path = MACRO_PATH) -> list[MacroEvent]:
    data = json.loads(path.read_text())
    events = [
        MacroEvent(date=date.fromisoformat(d), kind=kind)
        for kind in ("FOMC", "CPI")
        for d in data.get(kind, [])
    ]
    return sorted(events, key=lambda e: e.date)


def ex_dividend_from_info(info: dict[str, Any]) -> date | None:
    value = info.get("exDividendDate")
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), UTC).date()
    except TypeError, ValueError, OSError:
        return None


def build_events(
    today: date,
    next_earnings: date | None,
    ex_dividend: date | None,
    macro: list[MacroEvent],
    window_days: int = 30,
) -> Events:
    end = today + timedelta(days=window_days)
    within_7 = next_earnings is not None and 0 <= (next_earnings - today).days <= 7
    return Events(
        next_earnings=next_earnings,
        earnings_within_7d=within_7,
        next_ex_dividend=ex_dividend if ex_dividend and ex_dividend >= today else None,
        macro=[m for m in macro if today <= m.date <= end],
    )
