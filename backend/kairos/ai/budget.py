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

    def usage(self, now: datetime) -> dict[str, int]:
        minute, day = self._counts(now)
        return {"minute": minute, "day": day, "rpm": self.rpm, "rpd": self.rpd}
