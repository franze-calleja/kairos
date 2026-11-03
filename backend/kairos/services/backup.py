"""Daily SQLite backups to a folder outside the Docker volume, with retention."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from kairos.config import Settings
from kairos.db import get_meta, set_meta

log = logging.getLogger(__name__)


class BackupFailed(Exception):
    pass


def _local_day(settings: Settings, when: datetime) -> str:
    return when.astimezone(ZoneInfo(settings.tz)).date().isoformat()


def backup_due(settings: Settings, conn: sqlite3.Connection, now: datetime) -> bool:
    if not settings.backup_dir:
        return False
    last = get_meta(conn, "last_backup")
    return last is None or _local_day(settings, datetime.fromisoformat(last)) != _local_day(
        settings, now
    )


def backup_db(settings: Settings, conn: sqlite3.Connection, now: datetime) -> Path:
    """Copy the live database with SQLite's online backup API (safe while running, WAL included)."""
    if not settings.backup_dir:
        raise BackupFailed("Backups are turned off (BACKUP_DIR is empty)")
    folder = Path(settings.backup_dir)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"kairos-{_local_day(settings, now)}.db"
    tmp = target.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    dest = sqlite3.connect(tmp)
    try:
        conn.backup(dest)
        ok = dest.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        dest.close()
    if not ok:
        tmp.unlink(missing_ok=True)
        raise BackupFailed("Backup copy failed its integrity check; nothing was kept")
    tmp.replace(target)
    set_meta(conn, "last_backup", now.isoformat())
    for old in sorted(folder.glob("kairos-*.db"))[: -settings.backup_keep]:
        old.unlink(missing_ok=True)
    log.info("database backed up to %s", target)
    return target
