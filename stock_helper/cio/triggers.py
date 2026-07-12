from __future__ import annotations

from typing import Any

from stock_helper.config import load_yaml


def _cfg() -> dict[str, Any]:
    return load_yaml("cio.yaml")


def build_trigger_engine(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Layer 7 — If → Then trigger rules with live evaluation."""
    regime = snapshot.get("regime") or {}
    reasoning = snapshot.get("reasoning") or {}
    structure = snapshot.get("structure") or {}
    ind = regime.get("indicators") or {}

    ten_y = ind.get("ten_year_yield") or ind.get("dgs10")
    vix = ind.get("vix")
    cpi = ind.get("cpi_yoy_pct")
    breadth = (structure.get("breadth") or {}).get("signal", "")
    dom_topic = (reasoning.get("narrative_block") or {}).get("dominant_topic", "")

    triggers: list[dict[str, Any]] = []
    for rule in _cfg().get("triggers") or []:
        active = _eval_trigger(rule, ind, structure, reasoning)
        triggers.append(
            {
                "id": rule.get("id"),
                "if": rule.get("if"),
                "then": rule.get("then"),
                "active": active,
                "status": "TRIGGERED" if active else "watch",
            }
        )

    active_list = [t for t in triggers if t["active"]]
    return {
        "triggers": triggers,
        "active_triggers": active_list,
        "summary": f"{len(active_list)} active / {len(triggers)} monitored",
    }


def _eval_trigger(rule: dict, ind: dict, structure: dict, reasoning: dict) -> bool:
    metric = rule.get("metric")
    if metric == "ten_year_yield":
        val = ind.get("ten_year_yield") or ind.get("dgs10")
        if val is None:
            return False
        return float(val) > float(rule.get("threshold", 999))
    if metric == "vix":
        val = ind.get("vix")
        if val is None:
            return False
        return float(val) > float(rule.get("threshold", 999))

    signal = rule.get("signal")
    if signal == "breadth_improving":
        spread = (structure.get("breadth") or {}).get("daily_spread_pct")
        return spread is not None and float(spread) > 0.2
    if signal == "ai_earnings_risk":
        hyp = (reasoning.get("hypothesis_evolution") or {}).get("thesis_status", "")
        return hyp in ("WEAKEN", "INVALIDATED") and (reasoning.get("narrative_block") or {}).get("dominant_topic") == "ai"
    if signal == "inflation_risk":
        cpi = ind.get("cpi_yoy_pct")
        return cpi is not None and float(cpi) >= 3.5
    return False
