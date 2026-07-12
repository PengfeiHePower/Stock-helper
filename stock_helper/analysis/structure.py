from __future__ import annotations

from typing import Any

from stock_helper.analysis.factors import momentum_proxy, build_sector_rotation
from stock_helper.collectors.fundamentals import load_fundamentals_map
from stock_helper.config import load_yaml


def _structure_cfg() -> dict[str, Any]:
    return load_yaml("structure.yaml")


def _relative_performance(quote_a: dict, quote_b: dict) -> float | None:
    ca, cb = quote_a.get("c"), quote_b.get("c")
    pca, pcb = quote_a.get("pc"), quote_b.get("pc")
    if None in (ca, cb, pca, pcb) or pca == 0 or pcb == 0:
        return None
    ret_a = (ca - pca) / pca * 100
    ret_b = (cb - pcb) / pcb * 100
    return round(ret_a - ret_b, 2)


def build_market_structure(refresh: bool = False) -> dict[str, Any]:
    cfg = _structure_cfg()
    breadth = cfg.get("breadth") or {}
    eq = breadth.get("equal_weight", "RSP")
    cap = breadth.get("cap_weight", "SPY")
    growth = (cfg.get("growth_vs_broad") or {}).get("growth", "QQQ")
    broad = (cfg.get("growth_vs_broad") or {}).get("broad", "SPY")

    index_keys = list((cfg.get("indices") or {}).keys()) + [eq, cap, growth]
    index_keys = list(dict.fromkeys(index_keys))

    data = load_fundamentals_map(index_keys, refresh=refresh)
    indices_out: dict[str, Any] = {}

    for sym, meta in (cfg.get("indices") or {}).items():
        funds = data.get(sym.upper())
        if not funds:
            continue
        quote = funds.get("quote") or {}
        metric = funds.get("metric") or {}
        indices_out[sym] = {
            **meta,
            "ticker": sym,
            "price": quote.get("c"),
            "day_change_pct": quote.get("dp"),
            "momentum_52w": momentum_proxy(quote, metric),
        }

    rsp_data = data.get(eq.upper())
    spy_data = data.get(cap.upper())
    qqq_data = data.get(growth.upper())

    breadth_spread = None
    breadth_signal = "unknown"
    if rsp_data and spy_data:
        breadth_spread = _relative_performance(
            rsp_data.get("quote") or {}, spy_data.get("quote") or {}
        )
        thresholds = cfg.get("concentration") or {}
        narrow = float(thresholds.get("narrow_rally_threshold", -3.0))
        healthy = float(thresholds.get("healthy_breadth_threshold", 1.0))
        if breadth_spread is not None:
            if breadth_spread <= narrow:
                breadth_signal = "narrow_rally"
            elif breadth_spread >= healthy:
                breadth_signal = "broad_participation"
            else:
                breadth_signal = "mixed"

    growth_spread = None
    if qqq_data and spy_data:
        growth_spread = _relative_performance(
            qqq_data.get("quote") or {}, spy_data.get("quote") or {}
        )

    mag7 = []
    mag7_tickers = [m["ticker"] for m in (cfg.get("mag7") or [])]
    mag7_data = load_fundamentals_map(mag7_tickers, refresh=False)
    for item in cfg.get("mag7") or []:
        t = item["ticker"]
        funds = mag7_data.get(t.upper())
        if not funds:
            continue
        quote = funds.get("quote") or {}
        metric = funds.get("metric") or {}
        mag7.append(
            {
                "ticker": t,
                "day_change_pct": quote.get("dp"),
                "momentum_52w": momentum_proxy(quote, metric),
                "note": item.get("weight_note"),
            }
        )

    sectors = build_sector_rotation(refresh=False)
    leaders = sectors[:3] if sectors else []
    laggards = list(reversed(sectors[-3:])) if len(sectors) >= 3 else []

    return {
        "indices": indices_out,
        "breadth": {
            "equal_weight": eq,
            "cap_weight": cap,
            "daily_spread_pct": breadth_spread,
            "signal": breadth_signal,
            "interpretation": _breadth_interpretation(breadth_signal),
        },
        "growth_vs_broad": {
            "growth": growth,
            "broad": broad,
            "daily_spread_pct": growth_spread,
        },
        "sector_leaders": leaders,
        "sector_laggards": laggards,
        "mag7_leadership": mag7,
        "concentration": {
            "signal": breadth_signal,
            "note": (
                "RSP vs SPY is a breadth proxy: cap-weight beating equal-weight "
                "often means mega-caps are carrying the index."
            ),
        },
    }


def _breadth_interpretation(signal: str) -> str:
    return {
        "narrow_rally": "Index gains driven by a few large names — participation is narrow.",
        "broad_participation": "Gains are broad-based — healthier market structure.",
        "mixed": "No extreme breadth signal today — watch trend over weeks.",
        "unknown": "Breadth data unavailable.",
    }.get(signal, signal)
