from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from stock_helper.collectors.market import fetch_upcoming_earnings
from stock_helper.config import load_yaml
from stock_helper.watchlist import all_watchlist_tickers


def _cfg() -> dict[str, Any]:
    return load_yaml("cio.yaml")


def _earnings_cfg() -> dict[str, Any]:
    return load_yaml("cio_earnings.yaml").get("earnings_watch") or {}


def _importance_for(ticker: str) -> str:
    ecfg = _earnings_cfg()
    sym = ticker.upper()
    if sym in [t.upper() for t in ecfg.get("very_high") or []]:
        return "very_high"
    if sym in [t.upper() for t in ecfg.get("high") or []]:
        return "high"
    return "medium"


def _timing_label(event_date: str, today: date) -> str:
    try:
        d = date.fromisoformat(event_date)
    except (TypeError, ValueError):
        return "upcoming"
    delta = (d - today).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    if delta <= 7:
        return f"this_week ({d.strftime('%a %m/%d')})"
    if delta <= 14:
        return f"next_week ({d.strftime('%a %m/%d')})"
    return d.isoformat()


def _hour_label(hour: str) -> str:
    labels = {"bmo": "BMO", "amc": "AMC", "dmh": "intraday"}
    return labels.get((hour or "").lower(), hour or "TBD")


def _ticker_industry_map() -> dict[str, dict[str, str]]:
    """ticker → {industry_id, industry_name, theme_id}"""
    out: dict[str, dict[str, str]] = {}
    for iid, ind in (_cfg().get("industries") or {}).items():
        theme_id = ind.get("theme", "")
        for t in ind.get("tickers") or []:
            out[t.upper()] = {
                "industry_id": iid,
                "industry_name": ind.get("name", iid),
                "industry_name_zh": ind.get("name_zh", ind.get("name", iid)),
                "theme_id": theme_id,
            }
    return out


def cio_earnings_universe(
    industry_layer: dict[str, Any] | None = None,
    stock_layer: dict[str, Any] | None = None,
) -> list[str]:
    seen: set[str] = set()
    universe: list[str] = []

    for t in all_watchlist_tickers(include_agent=True):
        u = t.upper()
        if u not in seen:
            seen.add(u)
            universe.append(u)

    for iid, ind in (_cfg().get("industries") or {}).items():
        for t in ind.get("tickers") or []:
            u = t.upper()
            if u not in seen:
                seen.add(u)
                universe.append(u)

    for s in (stock_layer or {}).get("top_picks") or []:
        u = (s.get("ticker") or "").upper()
        if u and u not in seen:
            seen.add(u)
            universe.append(u)

    return universe


def build_earnings_watch(
    industry_layer: dict[str, Any] | None = None,
    stock_layer: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Finnhub earnings calendar → CIO watch list items."""
    ecfg = _earnings_cfg()
    horizon = int(ecfg.get("horizon_days", 14))
    max_items = int(ecfg.get("max_items", 12))
    today = date.today()

    universe = cio_earnings_universe(industry_layer, stock_layer)
    if not universe:
        return []

    events = fetch_upcoming_earnings(days=horizon, tickers=universe)
    ind_map = _ticker_industry_map()
    theme_names = {
        tid: t.get("name") for tid, t in (_cfg().get("themes") or {}).items()
    }
    theme_names_zh = {
        tid: t.get("name_zh") for tid, t in (_cfg().get("themes") or {}).items()
    }

    items: list[dict[str, Any]] = []
    for ev in events:
        sym = (ev.get("symbol") or "").upper()
        if not sym:
            continue
        ev_date = ev.get("date") or ""
        meta = ind_map.get(sym) or {}
        theme_id = meta.get("theme_id", "")
        importance = _importance_for(sym)
        timing = _timing_label(ev_date, today)
        hour = _hour_label(ev.get("hour", ""))

        items.append(
            {
                "event": f"{sym} Earnings",
                "event_zh": f"{sym} 财报",
                "ticker": sym,
                "date": ev_date,
                "timing": timing,
                "hour": hour,
                "importance": importance,
                "eps_estimate": ev.get("epsEstimate"),
                "revenue_estimate": ev.get("revenueEstimate"),
                "industry": meta.get("industry_name"),
                "industry_zh": meta.get("industry_name_zh"),
                "theme": theme_names.get(theme_id),
                "theme_zh": theme_names_zh.get(theme_id),
                "source": "finnhub_earnings",
            }
        )

    rank = {"very_high": 0, "high": 1, "medium": 2}
    items.sort(key=lambda x: (x.get("date", ""), rank.get(x.get("importance", "medium"), 9)))
    return items[:max_items]
