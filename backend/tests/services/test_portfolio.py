import json
from datetime import date

from kairos.services.portfolio import kairos_said


def reading(conn, ticker, created_at, lean="bullish", label="below_range"):
    payload = {"price": {"label": label}}
    conn.execute(
        "INSERT INTO readings (ticker, created_at, lean, confidence, ai_status, price_at, payload)"
        " VALUES (?, ?, ?, 'medium', 'ok', 100, ?)",
        (ticker, created_at, lean, json.dumps(payload)),
    )
    conn.commit()


def test_kairos_said_uses_reading_before_that_session_closed(conn):
    reading(conn, "NVDA", "2026-11-06T13:00:00+00:00")  # 21:00 Manila, before 16:00 NY
    said = kairos_said(conn, "NVDA", date(2026, 11, 6))
    assert said == {"price_label": "below_range", "lean": "bullish", "ai_status": "ok"}


def test_kairos_said_ignores_readings_after_close_or_too_old(conn):
    reading(conn, "NVDA", "2026-11-06T22:00:00+00:00")  # after the 21:00Z close
    reading(conn, "NVDA", "2026-11-05T04:00:00+00:00")  # 41h before the close
    assert kairos_said(conn, "NVDA", date(2026, 11, 6)) is None
