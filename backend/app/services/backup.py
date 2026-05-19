"""SQLite backup via sqlite3 .backup. Keeps last N days."""
from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from app.config import settings


log = logging.getLogger(__name__)


def _db_path() -> Path:
    url = settings.database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise RuntimeError(f"Backup only works for sqlite URLs, got {url!r}")
    return Path("/" + url[len(prefix):])


def run_backup() -> str:
    src = _db_path()
    if not src.exists():
        raise RuntimeError(f"DB file missing: {src}")
    backups_dir = Path(settings.data_dir) / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest = backups_dir / f"alerts_{stamp}.db"

    src_conn = sqlite3.connect(str(src))
    dst_conn = sqlite3.connect(str(dest))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    return str(dest)


def prune_old() -> int:
    backups_dir = Path(settings.data_dir) / "backups"
    if not backups_dir.exists():
        return 0
    cutoff = time.time() - settings.backup_keep_days * 86400
    pruned = 0
    for f in backups_dir.glob("alerts_*.db"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                pruned += 1
        except OSError:
            pass
    return pruned
