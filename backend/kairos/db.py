import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from kairos.config import Settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS lists (
    list_name TEXT NOT NULL CHECK (list_name IN ('holdings', 'watching')),
    ticker TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (list_name, ticker)
);
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    created_at TEXT NOT NULL,
    lean TEXT,
    confidence TEXT,
    ai_status TEXT NOT NULL,
    price_at REAL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readings_ticker_created ON readings (ticker, created_at);
CREATE TABLE IF NOT EXISTS outcomes (
    reading_id INTEGER NOT NULL REFERENCES readings(id),
    horizon INTEGER NOT NULL,
    price REAL NOT NULL,
    change_pct REAL NOT NULL,
    baseline_change_pct REAL,
    filled_at TEXT NOT NULL,
    PRIMARY KEY (reading_id, horizon)
);
CREATE TABLE IF NOT EXISTS budget (ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS discover (
    created_at TEXT NOT NULL,
    ticker TEXT NOT NULL,
    reason TEXT NOT NULL,
    score REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    trade_date TEXT NOT NULL,
    shares REAL NOT NULL CHECK (shares > 0),
    price REAL NOT NULL CHECK (price > 0),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades (ticker, trade_date, id);
"""


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


# Columns added after v1; existing databases get them on startup.
_ADDED_COLUMNS = {"lists": {"shares": "REAL", "thesis": "TEXT"}}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in _ADDED_COLUMNS.items():
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, sql_type in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")


def init_db(conn: sqlite3.Connection, settings: Settings) -> None:
    conn.executescript(SCHEMA)
    _migrate(conn)
    if get_meta(conn, "seeded") is None:
        from kairos.services.lists import add_ticker

        for ticker in settings.kairos_seed_holdings:
            add_ticker(conn, "holdings", ticker)
        for ticker in settings.kairos_seed_watching:
            add_ticker(conn, "watching", ticker)
        set_meta(conn, "seeded", datetime.now(UTC).isoformat())
    conn.commit()
