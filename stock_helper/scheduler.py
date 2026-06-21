from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from stock_helper.config import get_settings
from stock_helper.pipeline import run_full_brief_pipeline


def start_scheduler():
    settings = get_settings()
    tz = settings.brief_timezone
    sched = BlockingScheduler(timezone=tz)

    # Pre-market ~7:00 ET, post-close ~16:45 ET
    sched.add_job(
        lambda: run_full_brief_pipeline("morning"),
        CronTrigger(hour=7, minute=0, timezone=tz),
        id="morning_brief",
    )
    sched.add_job(
        lambda: run_full_brief_pipeline("close"),
        CronTrigger(hour=16, minute=45, timezone=tz),
        id="close_brief",
    )
    sched.start()
