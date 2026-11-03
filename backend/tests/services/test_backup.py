import sqlite3
from datetime import UTC, datetime, timedelta

from kairos.db import get_meta
from kairos.services import backup
from kairos.services.lists import add_ticker

NOW = datetime(2026, 11, 3, 1, 0, tzinfo=UTC)  # 09:00 in Manila


def test_backup_creates_a_consistent_copy(settings, conn, tmp_path):
    settings.backup_dir = str(tmp_path / "backups")
    add_ticker(conn, "holdings", "NVDA")  # committed but may still be in the WAL file
    path = backup.backup_db(settings, conn, NOW)
    assert path.name == "kairos-2026-11-03.db"
    copy = sqlite3.connect(path)
    assert copy.execute("SELECT ticker FROM lists").fetchall() == [("NVDA",)]
    assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert get_meta(conn, "last_backup") == NOW.isoformat()


def test_same_day_backup_replaces_the_file(settings, conn, tmp_path):
    settings.backup_dir = str(tmp_path / "backups")
    backup.backup_db(settings, conn, NOW)
    add_ticker(conn, "holdings", "VOO")
    path = backup.backup_db(settings, conn, NOW + timedelta(hours=2))
    assert len(list((tmp_path / "backups").glob("kairos-*.db"))) == 1
    assert ("VOO",) in sqlite3.connect(path).execute("SELECT ticker FROM lists").fetchall()


def test_retention_keeps_the_newest(settings, conn, tmp_path):
    settings.backup_dir = str(tmp_path / "backups")
    settings.backup_keep = 3
    for d in range(5):
        backup.backup_db(settings, conn, NOW + timedelta(days=d))
    names = sorted(p.name for p in (tmp_path / "backups").glob("kairos-*.db"))
    assert names == ["kairos-2026-11-05.db", "kairos-2026-11-06.db", "kairos-2026-11-07.db"]


def test_backup_due_once_per_local_day(settings, conn, tmp_path):
    settings.backup_dir = str(tmp_path / "backups")
    settings.tz = "Asia/Manila"
    assert backup.backup_due(settings, conn, NOW) is True
    backup.backup_db(settings, conn, NOW)
    assert (
        backup.backup_due(settings, conn, NOW + timedelta(hours=10)) is False
    )  # still Nov 3 in Manila
    assert (
        backup.backup_due(settings, conn, NOW + timedelta(hours=16)) is True
    )  # Nov 4, 01:00 Manila


def test_backups_can_be_disabled(settings, conn):
    settings.backup_dir = None
    assert backup.backup_due(settings, conn, NOW) is False
