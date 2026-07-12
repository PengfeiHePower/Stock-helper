from __future__ import annotations

from typing import Any

from stock_helper.cio.reasoning_chain import stars
from stock_helper.config import load_yaml


def _cfg() -> dict[str, Any]:
    return load_yaml("cio.yaml")


def build_monitoring_dashboard(
    snapshot: dict[str, Any],
    *,
    industry_layer: dict[str, Any] | None = None,
    stock_layer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Layer 8 — Market health + watch calendar."""
    regime = snapshot.get("regime") or {}
    structure = snapshot.get("structure") or {}
    sentiment = snapshot.get("sentiment") or {}
    reasoning = snapshot.get("reasoning") or {}
    ind = regime.get("indicators") or {}

    breadth_sig = (structure.get("breadth") or {}).get("signal", "mixed")
    breadth_score = {"healthy": 85, "mixed": 62, "narrow": 45, "narrow_rally": 48}.get(breadth_sig, 55)

    hy = ind.get("hy_spread")
    credit_score = 80 if hy is not None and float(hy) < 4 else 55 if hy else 65

    vix = float(ind.get("vix") or 18)
    liquidity_score = 75 if vix < 18 else 55 if vix < 25 else 35

    cpi = float(ind.get("cpi_yoy_pct") or 3)
    val_score = 40 if cpi >= 4 else 50 if cpi >= 3 else 60

    mag7 = structure.get("mag7_leadership") or []
    mom_score = 70 if mag7 and sum(float(m.get("day_change_pct") or 0) for m in mag7[:3]) > 0 else 50

    health = {
        "breadth": {"score": breadth_score, "rating": stars(breadth_score), "signal": breadth_sig},
        "credit": {"score": credit_score, "rating": stars(credit_score), "hy_spread": hy},
        "liquidity": {"score": liquidity_score, "rating": stars(liquidity_score), "vix": vix},
        "valuation": {"score": val_score, "rating": stars(val_score), "cpi_yoy": cpi},
        "momentum": {"score": mom_score, "rating": stars(mom_score)},
    }

    watch = _build_watch_list(
        sentiment, reasoning, snapshot,
        industry_layer=industry_layer,
        stock_layer=stock_layer,
    )
    earnings_watch = [w for w in watch if w.get("source") == "finnhub_earnings"]
    macro_watch = [w for w in watch if w.get("source") != "finnhub_earnings"]
    return {
        "market_health": health,
        "watch_list": watch,
        "earnings_calendar": earnings_watch,
        "macro_watch": macro_watch,
        "as_of": snapshot.get("report_month") or ind.get("as_of"),
    }


def _build_watch_list(
    sentiment: dict,
    reasoning: dict,
    snapshot: dict,
    *,
    industry_layer: dict[str, Any] | None = None,
    stock_layer: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    from stock_helper.cio.earnings_watch import build_earnings_watch

    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for ev in build_earnings_watch(industry_layer, stock_layer):
        key = f"earnings:{ev.get('ticker')}:{ev.get('date')}"
        if key not in seen:
            items.append(ev)
            seen.add(key)

    earnings_tickers = {ev.get("ticker") for ev in items if ev.get("ticker")}

    for row in _cfg().get("watch_keywords") or []:
        event = row.get("event", "")
        if event in seen:
            continue
        tickers = row.get("tickers") or []
        if tickers and all(t.upper() in earnings_tickers for t in tickers):
            continue
        importance = row.get("importance", "medium")
        for topic in sentiment.get("top_topics") or []:
            t = topic.get("topic", "").lower()
            if any(kw in t for kw in (row.get("keywords") or [])):
                items.append({
                    "event": event,
                    "timing": "upcoming",
                    "importance": importance,
                    "tickers": tickers,
                    "source": "macro_keyword",
                })
                seen.add(event)
                break

    for u in (reasoning.get("uncertainties") or [])[:4]:
        if isinstance(u, dict):
            label = u.get("label") or u.get("text", "")
            if label and label not in seen:
                items.append({
                    "event": label,
                    "timing": "near-term",
                    "importance": "high",
                    "tickers": [],
                    "source": "reasoning",
                })
                seen.add(label)

    scenarios = reasoning.get("scenarios") or []
    for s in scenarios[:2]:
        if isinstance(s, dict):
            w = s.get("watch") or s.get("trigger")
            if w and w not in seen:
                items.append({
                    "event": w,
                    "timing": "data-dependent",
                    "importance": "high",
                    "tickers": [],
                    "source": "scenario",
                })
                seen.add(w)

    if not any(i.get("source") == "finnhub_earnings" for i in items):
        for ev in build_earnings_watch(industry_layer, stock_layer):
            items.append(ev)

    return items[:14]
