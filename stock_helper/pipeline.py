from __future__ import annotations

from stock_helper.agents.classify import classify_news_batch
from stock_helper.agents.graph import run_daily_brief
from stock_helper.agents.recommender import auto_track_recommendations
from stock_helper.collectors.ingest import ingest_watchlist_news
from stock_helper.config import get_settings, slack_configured, telegram_brief_configured
from stock_helper.outputs.email_sender import send_brief_email
from stock_helper.watchlist import expire_agent_tracking


def run_full_brief_pipeline(session: str = "morning") -> str:
    from stock_helper.scripts.purge_agent_tracking import purge_invalid_agent_tracking

    purge_invalid_agent_tracking()
    expired = expire_agent_tracking()
    if expired:
        print(f"Expired {expired} agent-tracking tickers")

    added = ingest_watchlist_news()
    print(f"Ingested {added} new news items")

    classified = classify_news_batch(limit=25)
    if classified:
        print(f"Classified {classified} news items (L1)")

    recommendations = auto_track_recommendations()
    if recommendations:
        tickers = ", ".join(r["ticker"] for r in recommendations)
        print(f"Agent auto-tracked: {tickers}")

    brief = run_daily_brief(session=session)
    settings = get_settings()

    if send_brief_email(brief, session):
        print("Email sent")
    else:
        print("Email skipped (RESEND_API_KEY or EMAIL_TO not set)")

    if slack_configured():
        try:
            from stock_helper.outputs.slack_app import post_brief_to_slack

            post_brief_to_slack(brief, session)
            print("Slack brief posted")
        except Exception as e:
            print(f"Slack post failed: {e}")

    if telegram_brief_configured():
        try:
            from stock_helper.outputs.telegram_bot import post_brief_to_telegram

            post_brief_to_telegram(brief, session)
            print("Telegram brief posted")
        except Exception as e:
            print(f"Telegram post failed: {e}")

    return brief
