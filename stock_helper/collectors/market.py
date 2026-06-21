from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from stock_helper.collectors.finnhub import FinnhubClient
from stock_helper.watchlist import get_core_tickers


def fetch_core_quotes() -> list[dict[str, Any]]:
    client = FinnhubClient()
    quotes: list[dict[str, Any]] = []
    for symbol in get_core_tickers():
        q = client.quote(symbol)
        if not q or q.get("c") is None:
            continue
        prev = q.get("pc") or q.get("c")
        change_pct = ((q["c"] - prev) / prev * 100) if prev else 0.0
        quotes.append(
            {
                "symbol": symbol,
                "price": q.get("c"),
                "change_pct": round(change_pct, 2),
                "high": q.get("h"),
                "low": q.get("l"),
            }
        )
    return quotes


def format_quotes_markdown(quotes: list[dict[str, Any]]) -> str:
    if not quotes:
        return "_Market quotes unavailable (set FINNHUB_API_KEY)._"
    lines = ["| Ticker | Price | Chg % |", "|--------|-------|-------|"]
    for q in quotes:
        sign = "+" if q["change_pct"] >= 0 else ""
        lines.append(
            f"| {q['symbol']} | ${q['price']:.2f} | {sign}{q['change_pct']:.2f}% |"
        )
    return "\n".join(lines)


def fetch_upcoming_earnings(days: int = 7) -> list[dict[str, Any]]:
    client = FinnhubClient()
    start = date.today()
    end = start + timedelta(days=days)
    data = client.earnings_calendar(start.isoformat(), end.isoformat())
    items = data.get("earningsCalendar") or []
    core = set(get_core_tickers())
    filtered = [e for e in items if (e.get("symbol") or "").upper() in core]
    return sorted(filtered, key=lambda x: x.get("date", ""))[:10]


def format_earnings_markdown(events: list[dict[str, Any]]) -> str:
    if not events:
        return "_No upcoming earnings for core watchlist this week._"
    lines = []
    for e in events:
        sym = e.get("symbol", "?")
        dt = e.get("date", "?")
        hour = e.get("hour", "")
        eps_est = e.get("epsEstimate", "n/a")
        lines.append(f"- **{sym}** {dt} ({hour}) — EPS est: {eps_est}")
    return "\n".join(lines)
