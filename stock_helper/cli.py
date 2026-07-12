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
    p_brief.add_argument("--session", choices=["morning", "close", "weekly", "monthly"], default="morning")
    p_brief.add_argument(
        "--force",
        action="store_true",
        help="Run even on weekends or US market holidays",
    )

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

    p_analyze = sub.add_parser("analyze", help="Run monthly market & strategy report")
    p_analyze.add_argument("--refresh", action="store_true", help="Refresh fundamentals from API")

    p_monthly = sub.add_parser("monthly", help="Alias for analyze")
    p_monthly.add_argument("--refresh", action="store_true", help="Refresh fundamentals from API")

    p_biweekly = sub.add_parser("biweekly", help="Run biweekly structure+sentiment pulse")
    p_biweekly.add_argument("--refresh", action="store_true", help="Refresh quote/fundamentals cache")

    p_strategy = sub.add_parser("strategy", help="Run CIO strategy recommendation")
    p_strategy.add_argument("--level", choices=["L1", "L2", "L3"], default=None, help="Risk level")
    p_strategy.add_argument("--refresh", action="store_true", help="Refresh quote/fundamentals cache")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    if args.command == "ingest":
        from stock_helper.collectors.ingest import run_ingest

        n = run_ingest("cli")
        print(f"Added {n} news items")
        return 0

    if args.command == "status":
        from stock_helper.collectors.ingest import news_count
        from stock_helper.config import config_status
        from stock_helper.market_calendar import is_us_trading_day, trading_day_skip_reason
        from stock_helper.pipeline import run_full_brief_pipeline
        from stock_helper.storage.db import BriefRecord, CostLog, get_session
        from stock_helper.watchlist import all_watchlist_tickers, list_agent_tracking

        st = config_status()
        print("Configuration:")
        for k, v in st.items():
            print(f"  {k}: {'ok' if v else 'missing'}")
        print(f"\nUS trading day today: {is_us_trading_day()} ({trading_day_skip_reason()})")
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
        if args.session == "monthly":
            from stock_helper.analysis.pipeline import run_monthly_analysis_pipeline

            print(run_monthly_analysis_pipeline(refresh=False))
            return 0

        from stock_helper.pipeline import run_full_brief_pipeline

        brief = run_full_brief_pipeline(
            session=args.session,
            require_trading_day=not args.force,
        )
        if brief is None:
            return 0
        print(brief)
        return 0

    if args.command in ("analyze", "monthly"):
        from stock_helper.analysis.pipeline import run_monthly_analysis_pipeline

        print(run_monthly_analysis_pipeline(refresh=args.refresh))
        return 0

    if args.command == "biweekly":
        from stock_helper.analysis.pipeline import run_biweekly_analysis_pipeline

        print(run_biweekly_analysis_pipeline(refresh=args.refresh))
        return 0

    if args.command == "strategy":
        from stock_helper.analysis.report import build_phase1_snapshot
        from stock_helper.strategy.build import build_cio_strategy
        from stock_helper.strategy.cio_report import format_cio_markdown
        from stock_helper.strategy.snapshot import save_strategy_snapshot

        snap = build_phase1_snapshot(refresh=args.refresh)
        strategy = build_cio_strategy(snap, risk_level=args.level, refresh=args.refresh)
        save_strategy_snapshot(strategy)
        print(format_cio_markdown(strategy))
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
