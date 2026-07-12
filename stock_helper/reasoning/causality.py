from __future__ import annotations

from typing import Any


def build_causality_chains(
    regime: dict[str, Any],
    structure: dict[str, Any],
    breadth_deep: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Rule-based cause → effect chains from macro to indices."""
    dims = regime.get("dimension_labels") or {}
    ind = regime.get("indicators") or {}
    chains: list[dict[str, Any]] = []

    inflation = dims.get("inflation")
    policy = dims.get("policy")
    growth = dims.get("growth")
    risk = dims.get("risk")

    if inflation in ("elevated", "moderate"):
        steps = [
            {"node": "inflation", "label": f"Inflation {inflation}", "value": ind.get("cpi_yoy_pct")},
            {"node": "fed", "label": "Fed unlikely to ease aggressively", "value": ind.get("fed_funds")},
            {"node": "yields", "label": "Long-end yields elevated", "value": ind.get("ten_year_yield")},
            {"node": "multiples", "label": "Valuation multiple expansion harder"},
            {"node": "qqq", "label": "Growth/long-duration stocks face pressure", "value": "QQQ"},
        ]
        chains.append({"id": "inflation_policy", "steps": steps, "confidence": 0.78})

    if policy in ("restrictive", "neutral_tight"):
        steps = [
            {"node": "policy", "label": f"Policy {policy}", "value": ind.get("fed_funds")},
            {"node": "2y", "label": "Front-end yields anchored high", "value": ind.get("two_year_yield")},
            {"node": "tech", "label": "Tech sector sensitivity to rates"},
            {"node": "qqq", "label": "QQQ under pressure vs SPY", "value": (structure.get("growth_vs_broad") or {}).get("daily_spread_pct")},
        ]
        chains.append({"id": "tight_policy_tech", "steps": steps, "confidence": 0.72})

    if growth == "firm" and risk in ("calm", "moderate"):
        steps = [
            {"node": "growth", "label": "Growth firm", "value": growth},
            {"node": "credit", "label": "Credit conditions benign", "value": ind.get("hy_spread")},
            {"node": "spy", "label": "Broad equities supported", "value": "SPY"},
            {"node": "cyclicals", "label": "Cyclicals can outperform defensives"},
        ]
        chains.append({"id": "growth_support", "steps": steps, "confidence": 0.75})

    bd = breadth_deep or {}
    if bd.get("signal") == "narrow_rally" or (bd.get("participation_score") or 50) < 40:
        steps = [
            {"node": "breadth", "label": "Narrow participation", "value": bd.get("rsp_spy_spread")},
            {"node": "spy", "label": "SPY can rise on few names", "value": bd.get("returns", {}).get("SPY")},
            {"node": "rsp", "label": "Equal-weight lags", "value": bd.get("returns", {}).get("RSP")},
            {"node": "risk", "label": "Rally vulnerable to macro surprises"},
        ]
        chains.append({"id": "narrow_breadth", "steps": steps, "confidence": 0.7})

    if not chains:
        chains.append(
            {
                "id": "neutral",
                "steps": [
                    {"node": "macro", "label": "Macro mixed", "value": regime.get("regime")},
                    {"node": "indices", "label": "Index moves may be stock-specific"},
                ],
                "confidence": 0.5,
            }
        )
    return chains
