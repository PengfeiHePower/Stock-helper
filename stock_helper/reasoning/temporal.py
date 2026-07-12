from __future__ import annotations

from typing import Any


def build_temporal_views(
    regime: dict[str, Any],
    top_drivers: list[dict[str, Any]],
    narrative_block: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Short / medium / long horizon readings per key factor."""
    ind = regime.get("indicators") or {}
    dims = regime.get("dimension_labels") or {}
    main_topic = (narrative_block or {}).get("ranking", [None])[0]

    views: dict[str, dict[str, Any]] = {}

    ten_y = ind.get("ten_year_yield")
    if ten_y is not None:
        ty = float(ten_y)
        views["treasury_yield"] = {
            "short_term": _dir("headwind" if ty >= 4.2 else "neutral", "Rate pressure on multiples"),
            "medium_term": _dir("neutral", "Yields reflect restrictive-but-stable policy"),
            "long_term": _dir("tailwind" if dims.get("growth") == "firm" else "neutral", "Higher yields can reflect healthy nominal growth"),
        }

    if dims.get("inflation"):
        views["inflation"] = {
            "short_term": _dir("headwind" if dims["inflation"] == "elevated" else "neutral", "Sticky CPI limits Fed easing"),
            "medium_term": _dir("neutral", "Disinflation path still debated"),
            "long_term": _dir("tailwind" if dims["inflation"] == "cooling" else "headwind", "Inflation regime sets valuation ceiling"),
        }

    if main_topic == "ai":
        views["ai_narrative"] = {
            "short_term": _dir("tailwind", "Headline momentum + Mag7 leadership"),
            "medium_term": _dir("neutral", "Capex → profitability transition"),
            "long_term": _dir("uncertain", "Valuation sustainability unproven"),
        }

    for d in top_drivers[:3]:
        did = d.get("id")
        if did and did not in views:
            views[did] = {
                "short_term": _dir(d.get("direction", "neutral"), d.get("detail", "")),
                "medium_term": _dir("neutral", "Monitor persistence over weeks"),
                "long_term": _dir("neutral", "Structural factor — slow-moving"),
            }

    views["macro_regime"] = {
        "short_term": _dir("bullish" if dims.get("growth") == "firm" else "neutral", f"Growth {dims.get('growth', '—')}"),
        "medium_term": _dir("neutral", f"Policy {dims.get('policy', '—')}"),
        "long_term": _dir("bullish" if regime.get("regime") == "expansion" else "neutral", regime.get("regime", "mixed")),
    }
    return views


def _dir(direction: str, note: str) -> dict[str, str]:
    return {"direction": direction, "note": note}
