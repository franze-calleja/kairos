from datetime import date

from kairos.analysis.events import build_events, ex_dividend_from_info, load_macro
from kairos.models import MacroEvent

TODAY = date(2026, 11, 2)


def test_earnings_within_7d_boundaries():
    assert build_events(TODAY, date(2026, 11, 9), None, []).earnings_within_7d is True
    assert build_events(TODAY, date(2026, 11, 10), None, []).earnings_within_7d is False
    assert build_events(TODAY, None, None, []).earnings_within_7d is False


def test_macro_window():
    macro = [
        MacroEvent(date=date(2026, 11, 13), kind="CPI"),
        MacroEvent(date=date(2026, 12, 30), kind="FOMC"),
        MacroEvent(date=date(2026, 10, 28), kind="FOMC"),
    ]
    ev = build_events(TODAY, None, None, macro, window_days=30)
    assert [(m.kind, m.date) for m in ev.macro] == [("CPI", date(2026, 11, 13))]


def test_past_ex_dividend_is_none():
    assert build_events(TODAY, None, date(2026, 10, 1), []).next_ex_dividend is None
    assert build_events(TODAY, None, date(2026, 12, 1), []).next_ex_dividend == date(2026, 12, 1)


def test_ex_dividend_from_info_epoch():
    assert ex_dividend_from_info({"exDividendDate": 1796083200}) == date(2026, 12, 1)
    assert ex_dividend_from_info({}) is None


def test_macro_file_valid():
    events = load_macro()
    assert {e.kind for e in events} == {"FOMC", "CPI"}
    assert events == sorted(events, key=lambda e: e.date)
    assert MacroEvent(date=date(2026, 12, 9), kind="FOMC") in events
    assert MacroEvent(date=date(2026, 11, 10), kind="CPI") in events
