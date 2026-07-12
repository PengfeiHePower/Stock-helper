from __future__ import annotations

from stock_helper.analysis.report import run_biweekly_pulse, run_monthly_report
from stock_helper.config import slack_configured, telegram_brief_configured
from stock_helper.outputs.email_sender import send_brief_email


def _deliver_analysis_markdown(markdown: str, session: str) -> None:
    if send_brief_email(markdown, session):
        print(f"{session} report email sent")
    else:
        print(f"{session} report email skipped")

    if slack_configured():
        try:
            from stock_helper.outputs.slack_app import post_brief_to_slack

            post_brief_to_slack(markdown, session)
            print(f"{session} posted to Slack")
        except Exception as e:
            print(f"Slack {session} post failed: {e}")

    if telegram_brief_configured():
        try:
            from stock_helper.outputs.telegram_bot import post_brief_to_telegram

            post_brief_to_telegram(markdown, session)
            print(f"{session} posted to Telegram")
        except Exception as e:
            print(f"Telegram {session} post failed: {e}")


def run_monthly_analysis_pipeline(*, refresh: bool = False) -> str:
    markdown = run_monthly_report(refresh=refresh)
    _deliver_analysis_markdown(markdown, "monthly")
    return markdown


def run_biweekly_analysis_pipeline(*, refresh: bool = False) -> str:
    markdown = run_biweekly_pulse(refresh=refresh)
    _deliver_analysis_markdown(markdown, "biweekly")
    return markdown
