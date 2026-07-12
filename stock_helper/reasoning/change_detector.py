from __future__ import annotations

from typing import Any


def _dominant_narrative(sentiment: dict[str, Any], narratives: list[dict[str, Any]] | None) -> str:
    if narratives:
        return narratives[0].get("topic", "none")
    topics = sentiment.get("top_topics") or []
    return topics[0]["topic"] if topics else "none"


def _snapshot_summary(
    regime: dict[str, Any],
    structure: dict[str, Any],
    sentiment: dict[str, Any],
    conflict: dict[str, Any],
    drivers: list[dict[str, Any]],
    narratives: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    dims = regime.get("dimension_labels") or {}
    return {
        "regime": regime.get("regime"),
        "macro_inflation": dims.get("inflation"),
        "macro_growth": dims.get("growth"),
        "macro_policy": dims.get("policy"),
        "macro_risk": dims.get("risk"),
        "breadth_signal": (structure.get("breadth") or {}).get("signal"),
        "rsp_spy_spread": (structure.get("breadth") or {}).get("daily_spread_pct"),
        "qqq_spy_spread": (structure.get("growth_vs_broad") or {}).get("daily_spread_pct"),
        "sentiment_mood": sentiment.get("mood"),
        "dominant_narrative": _dominant_narrative(sentiment, narratives),
        "conflict_level": conflict.get("level"),
        "top_driver_id": drivers[0]["id"] if drivers else None,
    }


def detect_changes(
    current: dict[str, Any],
    prior: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not prior:
        return [
            {
                "field": "baseline",
                "label": "Prior snapshot",
                "prior": None,
                "current": "first run",
                "changed": True,
                "note": "No prior reasoning snapshot — changes tracked from next session.",
            }
        ]

    prior_sum = (prior or {}).get("change_summary") or (prior or {}).get("summary") or prior or {}
    changes: list[dict[str, Any]] = []

    fields = [
        ("regime", "Composite regime"),
        ("dominant_narrative", "Dominant narrative"),
        ("breadth_signal", "Breadth signal"),
        ("conflict_level", "Conflict level"),
        ("macro_policy", "Policy stance"),
        ("macro_growth", "Growth reading"),
        ("top_driver_id", "Top driver"),
        ("sentiment_mood", "Sentiment mood"),
    ]
    for key, label in fields:
        old = prior_sum.get(key)
        new = current.get(key)
        if old == new:
            changes.append(
                {"field": key, "label": label, "prior": old, "current": new, "changed": False}
            )
        else:
            changes.append(
                {
                    "field": key,
                    "label": label,
                    "prior": old,
                    "current": new,
                    "changed": True,
                    "note": _change_note(key, old, new),
                }
            )

    numeric = [
        ("rsp_spy_spread", "RSP vs SPY", 0.3),
        ("qqq_spy_spread", "QQQ vs SPY", 0.15),
    ]
    for key, label, threshold in numeric:
        old, new = prior_sum.get(key), current.get(key)
        if old is None or new is None:
            continue
        delta = abs(float(new) - float(old))
        changed = delta >= threshold
        changes.append(
            {
                "field": key,
                "label": label,
                "prior": old,
                "current": new,
                "changed": changed,
                "delta": round(delta, 2) if changed else None,
            }
        )
    return changes


def _change_note(key: str, old: Any, new: Any) -> str:
    if key == "dominant_narrative":
        return f"Market conversation shifted from {old} toward {new}."
    if key == "breadth_signal":
        return f"Participation changed: {old} → {new}."
    if key == "conflict_level":
        return f"Cross-layer tension moved {old} → {new}."
    if key == "top_driver_id":
        return f"Primary driver rotated from {old} to {new}."
    return f"{key} moved from {old} to {new}."


def build_change_summary(
    regime: dict[str, Any],
    structure: dict[str, Any],
    sentiment: dict[str, Any],
    conflict: dict[str, Any],
    drivers: list[dict[str, Any]],
    narratives: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    return _snapshot_summary(regime, structure, sentiment, conflict, drivers, narratives)
