from __future__ import annotations

from typing import Any


def build_counter_evidence(
    layer_signals: dict[str, dict[str, Any]],
    conflict: dict[str, Any],
    breadth_deep: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bull case vs bear case with confidence adjustment."""
    bull: list[str] = []
    bear: list[str] = []

    for layer, sig in layer_signals.items():
        reason = sig.get("reason", "")
        if sig.get("direction") == "bullish":
            bull.append(f"[{layer}] {reason}")
        elif sig.get("direction") == "bearish":
            bear.append(f"[{layer}] {reason}")

    if (breadth_deep or {}).get("participation_score", 50) < 40:
        bear.append("[breadth_deep] Participation score weak — rally lacks broad backing.")
    elif (breadth_deep or {}).get("participation_score", 50) > 65:
        bull.append("[breadth_deep] Participation score healthy — rally has breadth support.")

    level = conflict.get("level", "low")
    adjustment = {"low": 0.0, "moderate": -0.08, "high": -0.15}.get(level, 0.0)
    base_conf = conflict.get("overall_confidence", 0.6)
    adjusted = round(max(0.35, min(0.92, base_conf + adjustment)), 2)

    therefore = _therefore(bull, bear, level)

    return {
        "bullish_because": bull,
        "bearish_because": bear,
        "confidence_adjustment": adjustment,
        "adjusted_confidence": adjusted,
        "therefore": therefore,
    }


def _therefore(bull: list[str], bear: list[str], conflict_level: str) -> str:
    if conflict_level == "high":
        return "High cross-layer conflict — reduce conviction; wait for breadth or macro confirmation."
    if len(bull) >= 2 and len(bear) >= 1:
        return "Macro/flow arguments support risk, but counter-evidence caps upside — favor selectivity."
    if len(bull) >= 3:
        return "Evidence largely aligned bullish — higher conviction on risk-on positioning."
    if len(bear) >= 3:
        return "Defensive evidence dominates — prioritize capital preservation and quality."
    return "Mixed evidence — size positions for scenario uncertainty, not directional certainty."
