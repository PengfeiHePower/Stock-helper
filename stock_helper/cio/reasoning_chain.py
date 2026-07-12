from __future__ import annotations

from typing import Any


def stars(score: float) -> str:
    """Map 0–100 score to ★★★★★ rating."""
    n = max(1, min(5, round(score / 20)))
    return "★" * n + "☆" * (5 - n)


def stars_numeric(score: float) -> float:
    return round(max(1.0, min(5.0, score / 20)), 1)


def trend_label(delta: float) -> str:
    if delta >= 8:
        return "Strong"
    if delta >= 3:
        return "Improving"
    if delta <= -8:
        return "Weak"
    if delta <= -3:
        return "Softening"
    return "Stable"


def valuation_label(score: float) -> str:
    if score >= 70:
        return "Expensive"
    if score >= 45:
        return "Neutral"
    return "Cheap"


def build_investment_decision(
    *,
    entity_type: str,
    entity_id: str,
    entity_name: str,
    evidence: list[str],
    hypothesis: str,
    counter_evidence: list[str],
    decision: str,
    confidence: float,
    monitor: list[str] | None = None,
) -> dict[str, Any]:
    """Cross-cutting: Evidence → Hypothesis → Counter → Decision."""
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "evidence": evidence,
        "hypothesis": hypothesis,
        "counter_evidence": counter_evidence,
        "confidence": round(confidence, 2),
        "decision": decision,
        "monitor": monitor or [],
    }
