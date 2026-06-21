from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from stock_helper.config import ROOT


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Stock Helper — US equity personal assistant")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("ingest", help="Fetch news for watchlist")
    sub.add_parser("status", help="Show config and database status")

    p_brief = sub.add_parser("brief", help="Run daily brief pipeline")
    p_brief.add_argument("--session", choices=["morning", "close", "weekly"], default="morning")

    p_wl = sub.add_parser("watchlist", help="Manage agent tracking list")
    wl_sub = p_wl.add_subparsers(dest="wl_action")
    wl_sub.add_parser("show", help="Show watchlists")
    p_track = wl_sub.add_parser("track", help="Add ticker to agent tracking")
    p_track.add_argument("ticker")
    p_untrack = wl_sub.add_parser("untrack", help="Remove ticker from agent tracking")
    p_untrack.add_argument("ticker")
    p_recommend = wl_sub.add_parser("recommend", help="Show or apply agent recommendations")
    p_recommend.add_argument("--apply", action="store_true", help="Auto-add recommendations")

    sub.add_parser("alerts", help="Run one alert poll cycle (news + price)")
    sub.add_parser("schedule", help="Start scheduled brief jobs (blocking)")
    sub.add_parser("slack", help="Start Slack bot (Socket Mode)")
    sub.add_parser("telegram", help="Start Telegram bot (long polling)")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    if args.command == "ingest":
        from stock_helper.collectors.ingest import ingest_watchlist_news

        n = ingest_watchlist_news()
        print(f"Added {n} news items")
        return 0

    if args.command == "status":
        from stock_helper.collectors.ingest import news_count
        from stock_helper.config import config_status
        from stock_helper.storage.db import BriefRecord, CostLog, get_session
        from stock_helper.watchlist import all_watchlist_tickers, list_agent_tracking

        st = config_status()
        print("Configuration:")
        for k, v in st.items():
            print(f"  {k}: {'ok' if v else 'missing'}")
        print(f"\nWatchlist tickers: {len(all_watchlist_tickers())}")
        print(f"Agent tracking: {len(list_agent_tracking())}")
        print(f"News in DB: {news_count()}")

        session = get_session()
        briefs = session.query(BriefRecord).count()
        costs = session.query(CostLog).count()
        session.close()
        print(f"Briefs saved: {briefs}")
        print(f"LLM cost log entries: {costs}")
        return 0

    if args.command == "watchlist":
        from stock_helper.agents.recommender import auto_track_recommendations, recommend_tickers
        from stock_helper.watchlist import (
            add_agent_tracking,
            all_watchlist_tickers,
            get_core_tickers,
            get_list_tickers,
            list_agent_tracking,
            remove_agent_tracking,
        )

        if args.wl_action == "show" or not args.wl_action:
            print("Core:", ", ".join(get_core_tickers()))
            for name, syms in get_list_tickers().items():
                print(f"  {name}:", ", ".join(syms))
            agent = list_agent_tracking()
            if agent:
                print("Agent tracking:")
                for r in agent:
                    print(f"  {r['ticker']}: {r['reason']}")
            print(f"Total unique: {len(all_watchlist_tickers())}")
            return 0

        if args.wl_action == "track":
            _, msg = add_agent_tracking(args.ticker.upper(), "Added via CLI")
            print(msg)
            return 0

        if args.wl_action == "untrack":
            _, msg = remove_agent_tracking(args.ticker.upper())
            print(msg)
            return 0

        if args.wl_action == "recommend":
            if args.apply:
                added = auto_track_recommendations()
                if not added:
                    print("No new recommendations added.")
                for r in added:
                    print(f"  + {r['ticker']}: {r.get('status', r.get('reason'))}")
            else:
                picks = recommend_tickers()
                if not picks:
                    print("No recommendations right now.")
                for p in picks:
                    print(f"  {p['ticker']} ({p['mentions']} mentions) — {p['reason']}")
            return 0

        p_wl.print_help()
        return 1

    if args.command == "brief":
        from stock_helper.pipeline import run_full_brief_pipeline

        brief = run_full_brief_pipeline(session=args.session)
        print(brief)
        return 0

    if args.command == "alerts":
        from stock_helper.alerts.engine import run_alert_cycle

        sent = run_alert_cycle(force=True)
        print(f"Sent {sent} alert(s)")
        return 0

    if args.command == "schedule":
        from stock_helper.scheduler import start_scheduler

        print("Starting scheduler (Ctrl+C to stop)...")
        start_scheduler()
        return 0

    if args.command == "slack":
        from stock_helper.outputs.slack_app import run_slack_socket_mode

        print("Starting Slack bot...")
        run_slack_socket_mode()
        return 0

    if args.command == "telegram":
        from stock_helper.outputs.telegram_bot import run_telegram_bot

        run_telegram_bot()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
