from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from stock_helper.alerts.engine import load_alert_config, run_alert_cycle
from stock_helper.config import get_settings
from stock_helper.pipeline import run_full_brief_pipeline


def start_scheduler():
    settings = get_settings()
    tz = settings.brief_timezone
    sched = BlockingScheduler(timezone=tz)

    # Pre-market ~7:00 ET, post-close ~16:45 ET, weekly wrap Friday ~17:30 ET
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
    sched.add_job(
        lambda: run_full_brief_pipeline("weekly"),
        CronTrigger(day_of_week="fri", hour=17, minute=30, timezone=tz),
        id="weekly_brief",
    )

    alert_cfg = load_alert_config()
    if alert_cfg.get("enabled", True):
        interval = int(alert_cfg.get("poll_interval_minutes") or 10)
        sched.add_job(
            run_alert_cycle,
            IntervalTrigger(minutes=interval),
            id="watchlist_alerts",
            max_instances=1,
            coalesce=True,
        )

    sched.start()
