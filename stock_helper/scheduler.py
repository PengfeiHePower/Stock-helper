from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from stock_helper.alerts.engine import load_alert_config, run_alert_cycle
from stock_helper.config import get_settings, load_yaml
from stock_helper.market_calendar import (
    is_biweekly_trading_anchor,
    is_first_trading_day_of_month,
    is_us_trading_day,
    trading_day_skip_reason,
)
from stock_helper.pipeline import run_full_brief_pipeline


def _run_brief_if_trading_day(session: str) -> None:
    if not is_us_trading_day():
        print(f"Skipping {session} brief — {trading_day_skip_reason()}")
        return
    run_full_brief_pipeline(session, require_trading_day=False)


def _run_monthly_if_first_trading_day() -> None:
    cfg = load_yaml("analysis.yaml").get("monthly_report") or {}
    if not cfg.get("enabled", True):
        return
    if not is_first_trading_day_of_month():
        return
    from stock_helper.analysis.pipeline import run_monthly_analysis_pipeline

    print("Running monthly market & strategy report (first trading day of month)...")
    run_monthly_analysis_pipeline(refresh=True)


def _run_biweekly_if_anchor() -> None:
    cfg = load_yaml("analysis.yaml").get("biweekly_update") or {}
    if not cfg.get("enabled", True):
        return
    if not is_biweekly_trading_anchor():
        return
    if is_first_trading_day_of_month():
        print("Skipping biweekly pulse — full monthly report runs today.")
        return
    from stock_helper.analysis.pipeline import run_biweekly_analysis_pipeline

    print("Running biweekly market pulse...")
    run_biweekly_analysis_pipeline(refresh=False)


def start_scheduler():
    settings = get_settings()
    tz = settings.brief_timezone
    sched = BlockingScheduler(timezone=tz)

    sched.add_job(
        lambda: _run_brief_if_trading_day("morning"),
        CronTrigger(hour=7, minute=0, timezone=tz),
        id="morning_brief",
    )
    sched.add_job(
        lambda: _run_brief_if_trading_day("close"),
        CronTrigger(hour=16, minute=45, timezone=tz),
        id="close_brief",
    )
    sched.add_job(
        lambda: _run_brief_if_trading_day("weekly"),
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

    analysis_cfg = load_yaml("analysis.yaml")
    monthly = analysis_cfg.get("monthly_report") or {}
    if monthly.get("enabled", True):
        sched.add_job(
            _run_monthly_if_first_trading_day,
            CronTrigger(
                hour=int(monthly.get("hour", 8)),
                minute=int(monthly.get("minute", 0)),
                timezone=tz,
            ),
            id="monthly_analysis",
        )

    biweekly = analysis_cfg.get("biweekly_update") or {}
    if biweekly.get("enabled", True):
        sched.add_job(
            _run_biweekly_if_anchor,
            CronTrigger(
                hour=int(biweekly.get("hour", 8)),
                minute=int(biweekly.get("minute", 15)),
                timezone=tz,
            ),
            id="biweekly_analysis",
        )

    sched.start()
