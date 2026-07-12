from __future__ import annotations

from typing import Any

from stock_helper.analysis.formatting import note
from stock_helper.config import load_yaml


def risk_levels() -> dict[str, dict[str, Any]]:
    return load_yaml("analysis.yaml").get("risk_levels") or {}


def default_risk_level() -> str:
    return load_yaml("analysis.yaml").get("default_risk_level", "L2")


def allocation_for_regime(regime: str, level: str | None = None) -> dict[str, Any]:
    level = level or default_risk_level()
    levels = risk_levels()
    cfg = levels.get(level) or levels.get("L2") or {}

    regime_bias = {
        "expansion": {"equity_tilt": 1.05, "note": "Favor quality growth; watch valuation stretch."},
        "slowdown": {"equity_tilt": 0.85, "note": "Trim cyclical beta; add defensives and bonds."},
        "recession_risk": {"equity_tilt": 0.70, "note": "Capital preservation; quality + low beta."},
        "recovery": {"equity_tilt": 1.0, "note": "Balanced rebuild; mix recovery cyclicals and quality."},
    }
    bias = regime_bias.get(regime, regime_bias["recovery"])
    base_eq = float(cfg.get("equity_budget_pct", 65))
    adjusted_eq = round(min(95.0, base_eq * bias["equity_tilt"]), 1)

    return {
        "level": level,
        "label": cfg.get("label"),
        "label_zh": cfg.get("label_zh"),
        "equity_budget_pct": adjusted_eq,
        "max_single_stock_pct": cfg.get("max_single_stock_pct"),
        "style": cfg.get("style"),
        "regime_note": bias["note"],
        "non_equity_pct": round(100.0 - adjusted_eq, 1),
    }


def format_risk_levels_markdown(regime: str) -> str:
    lines = ["### Risk Level Allocation (6–12 month view)", ""]
    for level_id in ("L1", "L2", "L3"):
        alloc = allocation_for_regime(regime, level_id)
        lines.append(
            f"**{level_id} {alloc.get('label')}** — "
            f"Equity ~{alloc['equity_budget_pct']}%, "
            f"max single name {alloc['max_single_stock_pct']}%. "
            f"{note(alloc['regime_note'])}"
        )
    lines.append("")
    lines.append(note("Educational allocation template only — not a trade recommendation."))
    return "\n".join(lines)
