from __future__ import annotations

from typing import Any


def build_structure_why_chains(
    regime: dict[str, Any],
    structure: dict[str, Any],
    breadth_deep: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Why chains for index behavior — not just what happened."""
    ind = regime.get("indicators") or {}
    dims = regime.get("dimension_labels") or {}
    gspread = (structure.get("growth_vs_broad") or {}).get("daily_spread_pct")
    chains: list[dict[str, Any]] = []

    if gspread is not None and gspread < -0.05:
        steps = [
            {"node": "qqq_lag", "label": f"QQQ lagging SPY ({gspread}%)", "value": gspread},
        ]
        if ind.get("ten_year_yield") and float(ind["ten_year_yield"]) >= 4.0:
            steps.extend(
                [
                    {"node": "long_yield", "label": f"10Y yield elevated ({ind['ten_year_yield']}%)", "value": ind["ten_year_yield"]},
                    {"node": "duration", "label": "Duration compression on growth multiples"},
                    {"node": "valuation", "label": "Valuation multiple contraction risk"},
                ]
            )
        if dims.get("policy") in ("restrictive", "neutral_tight"):
            steps.insert(1, {"node": "policy", "label": f"Policy {dims.get('policy')}", "value": dims.get("policy")})
        chains.append(
            {
                "id": "qqq_underperform",
                "observation": "QQQ underperforming SPY",
                "steps": steps,
                "confidence": 0.68 if len(steps) >= 4 else 0.55,
            }
        )

    bd = breadth_deep or {}
    if (bd.get("leadership_score") or 0) >= 0.7 or (bd.get("participation_score") or 50) < 45:
        chains.append(
            {
                "id": "narrow_leadership",
                "observation": "Narrow market leadership",
                "steps": [
                    {"node": "mag7", "label": f"Mag7 avg {bd.get('mag7_avg_day_pct', '—')}%", "value": bd.get("mag7_avg_day_pct")},
                    {"node": "iwm", "label": f"IWM vs SPY {bd.get('iwm_spy_spread', '—')}%", "value": bd.get("iwm_spy_spread")},
                    {"node": "rsp", "label": f"RSP vs SPY {bd.get('rsp_spy_spread', '—')}%", "value": bd.get("rsp_spy_spread")},
                    {"node": "inference", "label": "Rally depends on mega-cap earnings, not broad economy"},
                ],
                "confidence": 0.72,
            }
        )

    return chains
