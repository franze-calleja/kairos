import sqlite3
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


class RequestBudget:
    """Counts Gemini requests in SQLite and refuses ones that would exceed rpm/rpd."""

    def __init__(self, conn: sqlite3.Connection, rpm: int, rpd: int, tz: str = "UTC") -> None:
        self.conn, self.rpm, self.rpd, self.tz = conn, rpm, rpd, ZoneInfo(tz)

    def _counts(self, now: datetime) -> tuple[int, int]:
        now_utc = now.astimezone(UTC)
        minute_ago = (now_utc - timedelta(seconds=60)).isoformat()
        local = now.astimezone(self.tz)
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
        q = "SELECT COUNT(*) FROM budget WHERE ts > ? AND ts <= ?"
        minute = self.conn.execute(q, (minute_ago, now_utc.isoformat())).fetchone()[0]
        day = self.conn.execute(
            "SELECT COUNT(*) FROM budget WHERE ts >= ? AND ts <= ?",
            (midnight.isoformat(), now_utc.isoformat()),
        ).fetchone()[0]
        return minute, day

    def try_acquire(self, now: datetime) -> bool:
        minute, day = self._counts(now)
        if minute >= self.rpm or day >= self.rpd:
            return False
        self.conn.execute("INSERT INTO budget (ts) VALUES (?)", (now.astimezone(UTC).isoformat(),))
        self.conn.commit()
        return True

    def day_exhausted(self, now: datetime) -> bool:
        return self.rpd <= 0 or self._counts(now)[1] >= self.rpd

    def seconds_until_slot(self, now: datetime) -> float | None:
        """0 if a request may go now, seconds to wait for the per-minute window, None if the
        daily budget (or a zero limit) means no request can be made today."""
        if self.rpm <= 0 or self.day_exhausted(now):
            return None
        minute, _ = self._counts(now)
        if minute < self.rpm:
            return 0
        now_utc = now.astimezone(UTC)
        rows = self.conn.execute(
            "SELECT ts FROM budget WHERE ts > ? AND ts <= ? ORDER BY ts DESC LIMIT ?",
            ((now_utc - timedelta(seconds=60)).isoformat(), now_utc.isoformat(), self.rpm),
        ).fetchall()
        oldest_in_window = datetime.fromisoformat(rows[-1]["ts"])
        return max((oldest_in_window + timedelta(seconds=60) - now_utc).total_seconds(), 0) + 0.1

    def usage(self, now: datetime) -> dict[str, int]:
        minute, day = self._counts(now)
        return {"minute": minute, "day": day, "rpm": self.rpm, "rpd": self.rpd}
