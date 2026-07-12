from __future__ import annotations

from typing import Any

from stock_helper.config import load_yaml


def _cfg() -> dict[str, Any]:
    return load_yaml("strategy.yaml")


def build_risk_management(
    snapshot: dict[str, Any],
    allocation: dict[str, Any],
) -> dict[str, Any]:
    """⑤ Risk Management — posture, triggers, and defensive actions."""
    cfg = _cfg()
    regime = snapshot.get("regime") or {}
    reasoning = snapshot.get("reasoning") or {}
    ind = regime.get("indicators") or {}

    vix = ind.get("vix")
    conflict = (reasoning.get("conflict") or {}).get("level", "low")
    thesis_status = (reasoning.get("hypothesis_evolution") or {}).get("thesis_status", "HOLD")
    uncertainties = reasoning.get("uncertainties") or []
    scenarios = reasoning.get("scenarios") or []

    equity_pct = float((allocation.get("weights") or {}).get("us_equity", 55))
    cash_pct = float((allocation.get("weights") or {}).get("cash", 10))

    score = 0
    if vix is not None:
        if float(vix) >= 28:
            score += 3
        elif float(vix) >= 20:
            score += 1
    if conflict == "high":
        score += 2
    elif conflict == "moderate":
        score += 1
    if thesis_status in ("WEAKEN", "INVALIDATED"):
        score += 2
    if equity_pct >= 70:
        score += 1

    posture_cfg = cfg.get("risk_posture") or {}
    if score >= 5:
        posture_key = "high"
    elif score >= 3:
        posture_key = "elevated"
    elif score >= 1:
        posture_key = "moderate"
    else:
        posture_key = "low"

    posture = posture_cfg.get(posture_key) or {"label": posture_key, "label_zh": posture_key}

    actions: list[str] = []
    if posture_key in ("elevated", "high"):
        actions.append("Reduce incremental equity exposure; favor cash and quality")
    if conflict == "high":
        actions.append("Wait for layer alignment before adding risk")
    if thesis_status == "WEAKEN":
        actions.append("Thesis weakening — tighten stops and review concentration")
    if thesis_status == "INVALIDATED":
        actions.append("Thesis invalidated — de-risk and reassess allocation")
    if vix is not None and float(vix) >= 28:
        actions.append("Volatility stress — cut leverage, widen cash buffer")
    if not actions:
        actions.append("Maintain strategic allocation; rebalance on drift > 5%")

    key_risks: list[str] = []
    for u in uncertainties[:4]:
        if isinstance(u, dict):
            key_risks.append(u.get("label") or u.get("text") or str(u))
        else:
            key_risks.append(str(u))
    for s in (scenarios if isinstance(scenarios, list) else scenarios.get("branches") or [])[:2]:
        if isinstance(s, dict):
            key_risks.append(s.get("name") or s.get("trigger", ""))

    dims = regime.get("dimension_labels") or {}
    if dims.get("inflation") in ("elevated", "moderate"):
        key_risks.append("Inflation / rates path")
    if dims.get("risk") in ("elevated", "stress"):
        key_risks.append("Risk-off shock")

    triggers = [
        {
            "signal": "VIX >= 28",
            "action": "Increase cash 5–8%, trim growth beta",
            "active": vix is not None and float(vix) >= 28,
        },
        {
            "signal": "Conflict high",
            "action": "Pause new risk; favor quality and bonds",
            "active": conflict == "high",
        },
        {
            "signal": "Thesis WEAKEN/INVALIDATED",
            "action": "Reduce concentration; review sector tilts",
            "active": thesis_status in ("WEAKEN", "INVALIDATED"),
        },
        {
            "signal": "Equity weight > 75%",
            "action": "Consider trim if risk posture elevated",
            "active": equity_pct > 75 and posture_key != "low",
        },
    ]

    return {
        "posture": posture_key,
        "posture_label": posture.get("label"),
        "posture_label_zh": posture.get("label_zh"),
        "risk_score": score,
        "equity_pct": equity_pct,
        "cash_pct": cash_pct,
        "actions": actions,
        "key_risks": list(dict.fromkeys(r for r in key_risks if r))[:6],
        "triggers": triggers,
        "thesis_status": thesis_status,
        "conflict_level": conflict,
        "vix": vix,
    }
