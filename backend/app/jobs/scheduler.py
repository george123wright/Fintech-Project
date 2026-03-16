from __future__ import annotations

import logging
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.services.refresh import run_nightly_refresh

logger = logging.getLogger(__name__)


def _nightly_runner(session_factory: Callable[[], Session]) -> None:
    try:
        with session_factory() as db:
            outcomes = run_nightly_refresh(db)
            logger.info("Nightly refresh finished for %d portfolio(s)", len(outcomes))
    except Exception as exc:
        logger.exception("Nightly refresh failed: %s", exc)


def start_scheduler(session_factory: Callable[[], Session], cron_expr: str) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    trigger = CronTrigger.from_crontab(cron_expr)
    scheduler.add_job(
        _nightly_runner,
        trigger=trigger,
        args=[session_factory],
        id="nightly-refresh",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started with cron '%s'", cron_expr)
    return scheduler
