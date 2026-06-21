from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from stock_helper.collectors.finnhub import FinnhubClient
from stock_helper.config import load_yaml
from stock_helper.watchlist import all_watchlist_tickers, get_core_tickers


def fetch_quotes(symbols: list[str]) -> list[dict[str, Any]]:
    client = FinnhubClient()
    quotes: list[dict[str, Any]] = []
    for symbol in symbols:
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


def fetch_core_quotes() -> list[dict[str, Any]]:
    return fetch_quotes(get_core_tickers())


def get_etf_tickers() -> list[str]:
    return list(load_yaml("watchlist.yaml").get("etfs") or [])


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


def fetch_upcoming_earnings(
    days: int = 7, tickers: list[str] | None = None
) -> list[dict[str, Any]]:
    client = FinnhubClient()
    start = date.today()
    end = start + timedelta(days=days)
    data = client.earnings_calendar(start.isoformat(), end.isoformat())
    items = data.get("earningsCalendar") or []
    watch = set(tickers or all_watchlist_tickers(include_agent=True))
    filtered = [e for e in items if (e.get("symbol") or "").upper() in watch]
    return sorted(filtered, key=lambda x: (x.get("date", ""), x.get("symbol", "")))[:20]


def _hour_label(hour: str) -> str:
    labels = {"bmo": "pre-market (BMO)", "amc": "after close (AMC)", "dmh": "during session"}
    return labels.get((hour or "").lower(), hour or "TBD")


def _format_earnings_line(event: dict[str, Any]) -> str:
    sym = event.get("symbol", "?")
    dt = event.get("date", "?")
    hour = _hour_label(event.get("hour", ""))
    eps_est = event.get("epsEstimate", "n/a")
    return f"- **{sym}** {dt} ({hour}) — EPS est: {eps_est}"


def format_earnings_markdown(
    events: list[dict[str, Any]], session: str = "morning"
) -> str:
    if not events:
        return "_No upcoming earnings on watchlist this week._"

    today = date.today()
    tomorrow = today + timedelta(days=1)
    today_s = today.isoformat()
    tomorrow_s = tomorrow.isoformat()

    if session == "weekly":
        next_week_end = today + timedelta(days=7)
        next_week_end_s = next_week_end.isoformat()
        upcoming = [
            e for e in events if today_s <= (e.get("date") or "") <= next_week_end_s
        ]
        sections = ["**Next 7 days (watchlist):**"]
        if upcoming:
            sections.extend(_format_earnings_line(e) for e in upcoming)
        else:
            sections.append("_None scheduled._")
        later = [e for e in events if (e.get("date") or "") > next_week_end_s]
        if later:
            sections.extend(["", "**Later:**"])
            sections.extend(_format_earnings_line(e) for e in later[:8])
        return "\n".join(sections)

    if session == "close":
        tonight = [
            e
            for e in events
            if e.get("date") == today_s and (e.get("hour") or "").lower() == "amc"
        ]
        tomorrow_open = [
            e
            for e in events
            if e.get("date") == tomorrow_s and (e.get("hour") or "").lower() == "bmo"
        ]
        later = [e for e in events if e not in tonight and e not in tomorrow_open]
        sections: list[str] = []
        sections.append("**Tonight (after close):**")
        if tonight:
            sections.extend(_format_earnings_line(e) for e in tonight)
        else:
            sections.append("_None scheduled._")
        sections.append("")
        sections.append("**Tomorrow pre-market:**")
        if tomorrow_open:
            sections.extend(_format_earnings_line(e) for e in tomorrow_open)
        else:
            sections.append("_None scheduled._")
        if later:
            sections.append("")
            sections.append("**Later this week:**")
            sections.extend(_format_earnings_line(e) for e in later[:8])
        return "\n".join(sections)

    today_events = [e for e in events if e.get("date") == today_s]
    week_events = [e for e in events if e.get("date") != today_s]
    sections = ["**Today / tonight:**"]
    if today_events:
        sections.extend(_format_earnings_line(e) for e in today_events)
    else:
        sections.append("_None on watchlist today._")
    if week_events:
        sections.extend(["", "**Rest of week (watchlist):**"])
        sections.extend(_format_earnings_line(e) for e in week_events)
    return "\n".join(sections)


def _load_ipo_config() -> dict:
    return load_yaml("ipos.yaml")


def _format_usd(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    amount = float(value)
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.1f}B"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.0f}M"
    return f"${amount:,.0f}"


def _ipo_watch_needles(cfg: dict) -> list[str]:
    needles: list[str] = []
    for item in cfg.get("watch") or []:
        if isinstance(item, str):
            needles.append(item.strip().lower())
        elif isinstance(item, dict):
            for key in ("name", "symbol"):
                val = (item.get(key) or "").strip()
                if val:
                    needles.append(val.lower())
    return [n for n in needles if n]


def _matches_ipo_watch(event: dict[str, Any], needles: list[str]) -> bool:
    if not needles:
        return False
    name = (event.get("name") or "").lower()
    symbol = (event.get("symbol") or "").lower()
    return any(n in name or n == symbol or n in symbol for n in needles)


def _is_notable_ipo(event: dict[str, Any], cfg: dict) -> tuple[bool, str]:
    status = (event.get("status") or "").lower()
    if status == "withdrawn":
        return False, ""

    if _matches_ipo_watch(event, _ipo_watch_needles(cfg)):
        return True, "watchlist"

    min_val = float(cfg.get("min_deal_value_usd") or 0)
    total = event.get("totalSharesValue") or 0
    if cfg.get("auto_notable", True) and min_val and total and float(total) >= min_val:
        return True, "large deal"

    return False, ""


def fetch_upcoming_ipos(days: int | None = None) -> list[dict[str, Any]]:
    cfg = _load_ipo_config()
    if not cfg.get("enabled", True):
        return []

    client = FinnhubClient()
    if not client.api_key:
        return []

    start = date.today()
    horizon = days if days is not None else int(cfg.get("lookahead_days") or 45)
    end = start + timedelta(days=horizon)
    data = client.ipo_calendar(start.isoformat(), end.isoformat())
    items = data.get("ipoCalendar") or []

    notable: list[dict[str, Any]] = []
    for event in items:
        include, reason = _is_notable_ipo(event, cfg)
        if include:
            enriched = dict(event)
            enriched["notable_reason"] = reason
            notable.append(enriched)

    return sorted(notable, key=lambda x: (x.get("date", ""), x.get("symbol", "")))[:15]


def _format_ipo_line(event: dict[str, Any]) -> str:
    symbol = event.get("symbol") or "TBD"
    name = event.get("name") or "Unknown"
    dt = event.get("date") or "?"
    exchange = event.get("exchange") or "?"
    price = event.get("price") or "TBD"
    deal = _format_usd(event.get("totalSharesValue"))
    status = event.get("status") or "expected"
    reason = event.get("notable_reason") or "notable"
    tag = {"watchlist": "⭐ watch", "large deal": "💰 large"}.get(reason, reason)
    return (
        f"- **{symbol}** — {name} · {dt} · {exchange} · "
        f"{price}/sh · {deal} · _{status}_ · {tag}"
    )


def format_ipos_markdown(events: list[dict[str, Any]], session: str = "morning") -> str:
    cfg = _load_ipo_config()
    if not cfg.get("enabled", True):
        return "_IPO calendar disabled in config/ipos.yaml._"

    if not FinnhubClient().api_key:
        return "_IPO calendar unavailable (set FINNHUB_API_KEY)._"

    if not events:
        watch = ", ".join(_ipo_watch_needles(cfg)[:6]) or "none"
        return (
            "_No matching star IPOs on the calendar in the next "
            f"{cfg.get('lookahead_days', 45)} days._ "
            f"Add names in `config/ipos.yaml` (watch: {watch}…)."
        )

    today = date.today()
    week_end = today + timedelta(days=7)
    today_s = today.isoformat()
    week_end_s = week_end.isoformat()

    this_week = [
        e for e in events if today_s <= (e.get("date") or "") <= week_end_s
    ]
    later = [e for e in events if e not in this_week]

    if session == "close":
        sections: list[str] = ["**Next 7 days:**"]
        if this_week:
            sections.extend(_format_ipo_line(e) for e in this_week)
        else:
            sections.append("_None on the star IPO radar this week._")
        if later:
            sections.extend(["", "**Later (still on radar):**"])
            sections.extend(_format_ipo_line(e) for e in later[:5])
        return "\n".join(sections)

    sections = ["**Next 7 days:**"]
    if this_week:
        sections.extend(_format_ipo_line(e) for e in this_week)
    else:
        sections.append("_None this week._")
    if later:
        sections.extend(["", f"**Later (up to {cfg.get('lookahead_days', 45)} days):**"])
        sections.extend(_format_ipo_line(e) for e in later)
    return "\n".join(sections)
