from __future__ import annotations

from typing import Any

from stock_helper.cio.reasoning_chain import build_investment_decision


def build_regime_layer(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Layer 1 — Market Regime only. No strategy yet."""
    regime = snapshot.get("regime") or {}
    reasoning = snapshot.get("reasoning") or {}
    structure = snapshot.get("structure") or {}
    thesis = reasoning.get("thesis") or {}
    sub = (reasoning.get("signals") or {}).get("sub_regime") or {}
    conflict = reasoning.get("conflict") or {}
    drivers = reasoning.get("top_drivers") or []
    dims = regime.get("dimension_labels") or {}

    label = sub.get("label") or regime.get("regime", "").replace("_", " ").title()
    label_zh = _regime_zh(sub.get("primary") or regime.get("regime", ""))

    narrative = thesis.get("body") or thesis.get("headline") or ""
    if not narrative:
        narrative = _default_narrative(regime, structure, reasoning)

    key_drivers = []
    for d in drivers[:5]:
        key_drivers.append(d.get("label") or d.get("driver") or str(d))
    if not key_drivers:
        key_drivers = [dims.get(k, k).title() for k in ("growth", "inflation", "policy", "risk")]

    supports = conflict.get("supports") or []
    headwinds = conflict.get("headwinds") or []
    conflict_chain = []
    if supports:
        conflict_chain.append(supports[0] if isinstance(supports[0], str) else supports[0].get("text", ""))
    if headwinds:
        conflict_chain.append(headwinds[0] if isinstance(headwinds[0], str) else headwinds[0].get("text", ""))
    breadth = (structure.get("breadth") or {}).get("interpretation", "")
    if breadth:
        conflict_chain.append(breadth)

    overall = conflict.get("summary") or "Constructive but fragile."
    confidence = thesis.get("overall_confidence")
    if confidence is None:
        confidence = (reasoning.get("signals") or {}).get("overall_confidence", 0.5)

    reasoning_decision = build_investment_decision(
        entity_type="regime",
        entity_id=regime.get("regime", "unknown"),
        entity_name=label,
        evidence=[
            f"Composite: {regime.get('regime')}",
            f"Sub-regime: {sub.get('primary', '—')}",
            f"Conflict: {conflict.get('level', 'low')}",
        ],
        hypothesis=thesis.get("headline") or overall,
        counter_evidence=[str(h) for h in headwinds[:3]],
        decision="Monitor — regime layer does not prescribe trades",
        confidence=float(confidence) if confidence else 0.5,
        monitor=[u.get("label", "") for u in (reasoning.get("uncertainties") or [])[:3] if isinstance(u, dict)],
    )

    return {
        "current_regime": label,
        "current_regime_zh": label_zh,
        "composite": regime.get("regime"),
        "sub_regime": sub.get("primary"),
        "confidence": confidence,
        "confidence_label": _confidence_label(confidence),
        "market_narrative": narrative,
        "market_narrative_zh": thesis.get("headline_zh") or narrative,
        "key_drivers": key_drivers,
        "key_conflict": {
            "chain": [c for c in conflict_chain if c],
            "overall": overall,
        },
        "dimensions": dims,
        "reasoning": reasoning_decision,
    }


def _regime_zh(tag: str) -> str:
    return {
        "late_cycle": "晚期扩张",
        "selective_risk_on": "选择性风险偏好",
        "expansion": "扩张",
        "slowdown": "放缓",
        "recession_risk": "衰退风险",
        "recovery": "复苏",
    }.get(tag, tag.replace("_", " "))


def _confidence_label(c: Any) -> str:
    if c is None:
        return "Moderate"
    try:
        v = float(c)
    except (TypeError, ValueError):
        return "Moderate"
    if v >= 0.75:
        return "High"
    if v >= 0.5:
        return "Moderate"
    return "Low"


def _default_narrative(regime: dict, structure: dict, reasoning: dict) -> str:
    dims = regime.get("dimension_labels") or {}
    breadth = (structure.get("breadth") or {}).get("signal", "mixed")
    topic = (reasoning.get("narrative_block") or {}).get("dominant_topic", "macro")
    return (
        f"The economy reads as {dims.get('growth', 'mixed')} growth with "
        f"{dims.get('inflation', 'mixed')} inflation. Equity leadership is "
        f"{breadth}; dominant narrative is {topic}. "
        "Elevated yields may limit broad valuation expansion."
    )
