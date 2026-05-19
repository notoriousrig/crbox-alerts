"""APScheduler bootstrap.

Periodic RSS poll (every POLL_INTERVAL_MINUTES) + nightly SQLite backup
+ daily prune of stale item rows.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings


log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _run_poll() -> None:
    from app.services.rss_poller import poll_all
    log.info("Scheduled RSS poll starting")
    try:
        result = poll_all()
        log.info("Poll done: %s", result.as_dict())
    except Exception:
        log.exception("RSS poll failed")


def _run_prune() -> None:
    from app.services.rss_poller import prune_old_items
    try:
        n = prune_old_items()
        if n:
            log.info("Pruned %d stale item rows", n)
    except Exception:
        log.exception("Prune failed")


def _run_backup() -> None:
    from app.services.backup import run_backup, prune_old
    log.info("Nightly SQLite backup starting")
    try:
        path = run_backup()
        log.info("Backup written to %s", path)
        prune_old()
    except Exception:
        log.exception("Backup failed")


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_poll,
        IntervalTrigger(minutes=max(5, settings.poll_interval_minutes)),
        id="rss_poll",
        replace_existing=True,
        next_run_time=None,  # don't fire immediately on boot
    )
    _scheduler.add_job(
        _run_prune,
        CronTrigger(hour=settings.backup_hour, minute=30),
        id="prune",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_backup,
        CronTrigger(hour=settings.backup_hour, minute=0),
        id="backup",
        replace_existing=True,
    )
    _scheduler.start()
    log.info(
        "Scheduler started — RSS poll every %dm, backup @ %02d:00 UTC",
        settings.poll_interval_minutes, settings.backup_hour,
    )


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
