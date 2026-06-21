from __future__ import annotations

from collections import Counter

from stock_helper.collectors.ingest import load_recent_news
from stock_helper.config import load_yaml
from stock_helper.validators import is_valid_ticker
from stock_helper.watchlist import (
    add_agent_tracking,
    all_watchlist_tickers,
    get_agent_tracking_tickers,
)


def tickers_from_news_item(item: dict) -> list[str]:
    # Only use Finnhub company news symbols — SEC ticker lists include preferred share classes
    if item.get("source") != "finnhub":
        return []

    found: list[str] = []
    for part in (item.get("tickers") or "").split(","):
        t = part.strip().upper()
        if is_valid_ticker(t):
            found.append(t)
    return found


def recommend_tickers(limit: int = 5) -> list[dict]:
    cfg = load_yaml("watchlist.yaml").get("agent_tracking") or {}
    if not cfg.get("enabled", True):
        return []

    already = set(all_watchlist_tickers(include_agent=True))
    counter: Counter[str] = Counter()

    for item in load_recent_news(limit=100):
        for t in tickers_from_news_item(item):
            if t not in already:
                counter[t] += 1

    max_size = cfg.get("max_size", 15)
    slots = max(0, max_size - len(get_agent_tracking_tickers()))
    if slots == 0:
        return []

    picks: list[dict] = []
    for ticker, count in counter.most_common(limit + 10):
        if count < 2 or not is_valid_ticker(ticker):
            continue
        picks.append(
            {
                "ticker": ticker,
                "mentions": count,
                "reason": f"Mentioned in {count} recent news items",
            }
        )
        if len(picks) >= min(limit, slots):
            break
    return picks


def auto_track_recommendations(dry_run: bool = False) -> list[dict]:
    added: list[dict] = []
    for pick in recommend_tickers():
        if dry_run:
            added.append(pick)
            continue
        ok, msg = add_agent_tracking(pick["ticker"], pick["reason"])
        if ok:
            added.append({**pick, "status": msg})
    return added
