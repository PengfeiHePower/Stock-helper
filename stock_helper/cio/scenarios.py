from __future__ import annotations

from typing import Any


def build_scenario_planning(
    snapshot: dict[str, Any],
    portfolio_layer: dict[str, Any],
) -> dict[str, Any]:
    """Layer 6 — Base / Bull / Bear scenario branches."""
    regime = snapshot.get("regime") or {}
    reasoning = snapshot.get("reasoning") or {}
    raw_scenarios = reasoning.get("scenarios") or []

    base_prob = 50
    bull_prob = 25
    bear_prob = 25

    scenarios = [
        {
            "id": "base",
            "name": "Base",
            "name_zh": "基准",
            "probability_pct": base_prob,
            "narrative": "Expansion continues with selective leadership; maintain strategic allocation.",
            "narrative_zh": "扩张延续、行情仍有选择性；维持战略配置。",
            "portfolio_action": "Hold current model portfolio",
        },
        {
            "id": "bull",
            "name": "Bull",
            "name_zh": "乐观",
            "probability_pct": bull_prob,
            "narrative": "Inflation falls → yields decline → breadth broadens → add small cap / RSP.",
            "narrative_zh": "通胀下行 → 收益率回落 → 广度改善 → 增配小盘/RSP。",
            "portfolio_action": "Increase RSP/IWM, trim cash, add cyclicals",
        },
        {
            "id": "bear",
            "name": "Bear",
            "name_zh": "悲观",
            "probability_pct": bear_prob,
            "narrative": "Inflation reaccelerates → yields up → reduce growth → raise cash.",
            "narrative_zh": "通胀再加速 → 收益率上行 → 减成长 → 增现金。",
            "portfolio_action": "Reduce QQQ/SMH, raise cash 5–10%, add TLT",
        },
    ]

    for raw in raw_scenarios[:3]:
        trigger = raw.get("trigger", "")
        prob = raw.get("probability_pct", 0)
        if "below" in trigger.lower() or "beat" in trigger.lower():
            scenarios[1]["probability_pct"] = max(scenarios[1]["probability_pct"], prob)
        elif "above" in trigger.lower() or "miss" in trigger.lower() or "risk" in trigger.lower():
            scenarios[2]["probability_pct"] = max(scenarios[2]["probability_pct"], prob)

    total = sum(s["probability_pct"] for s in scenarios) or 1
    for s in scenarios:
        s["probability_pct"] = round(100 * s["probability_pct"] / total)

    return {
        "scenarios": scenarios,
        "raw_branches": raw_scenarios[:5],
        "update_frequency": "daily",
    }
