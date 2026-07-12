from __future__ import annotations

from typing import Any

from stock_helper.analysis.formatting import fmt_num, note, support_line


def explain_index_behavior(
    regime: dict[str, Any],
    structure: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Rule-based links between macro dimensions + structure and SPY/QQQ/DIA behavior.
    Each item: claim, support, confidence.
    """
    dims = regime.get("dimension_labels") or {}
    if not dims and regime.get("dimensions"):
        dims = {k: v.get("label") for k, v in regime["dimensions"].items()}

    indices = structure.get("indices") or {}
    breadth = structure.get("breadth") or {}
    growth_spread = (structure.get("growth_vs_broad") or {}).get("daily_spread_pct")

    explanations: list[dict[str, Any]] = []

    for sym in ("SPY", "QQQ", "DIA"):
        idx = indices.get(sym)
        if not idx:
            continue
        day_chg = idx.get("day_change_pct")
        mom = idx.get("momentum_52w")
        claims: list[str] = []
        support: list[str] = []

        if sym == "QQQ":
            if dims.get("policy") in ("restrictive", "neutral_tight"):
                claims.append("Growth/tech can face headwinds when policy is tight.")
                support.append(f"policy={dims.get('policy')}")
            if dims.get("growth") == "slowing":
                claims.append("Slowing growth often pressures high-duration tech multiples.")
                support.append(f"growth={dims.get('growth')}")
            if growth_spread is not None and growth_spread < 0:
                claims.append("QQQ lagging SPY today — growth underperforming broad market.")
                support.append(f"QQQ-SPY daily spread {growth_spread}%")

        if sym == "SPY":
            if breadth.get("signal") == "narrow_rally":
                claims.append("SPY may look fine while breadth is weak — few giants lifting the index.")
                support.append(f"RSP-SPY spread {breadth.get('daily_spread_pct')}%")
            elif breadth.get("signal") == "broad_participation":
                claims.append("Broad participation supports SPY moves — rally has wider backing.")
                support.append(f"breadth={breadth.get('signal')}")

        if sym == "DIA":
            if dims.get("risk") == "elevated":
                claims.append("Blue chips can act relatively defensive in elevated risk regimes.")
                support.append(f"risk={dims.get('risk')}")

        if dims.get("inflation") == "elevated" and dims.get("policy") == "restrictive":
            claims.append("Inflation + tight policy combo tends to cap multiple expansion.")
            support.append(
                f"inflation={dims.get('inflation')}, policy={dims.get('policy')}"
            )

        if not claims:
            claims.append("No strong macro-structure conflict signal — moves may be stock-specific.")
            support.append("neutral composite")

        explanations.append(
            {
                "index": sym,
                "name": idx.get("name", sym),
                "day_change_pct": day_chg,
                "momentum_52w": mom,
                "claims": claims,
                "support": support,
                "confidence": _confidence(len(support), breadth.get("signal")),
                "caveat": "Daily moves are noisy; use monthly trend for long-term view.",
            }
        )

    return explanations


def _confidence(support_count: int, breadth_signal: str | None) -> float:
    base = 0.45 + min(0.35, support_count * 0.1)
    if breadth_signal in ("narrow_rally", "broad_participation"):
        base += 0.1
    return round(min(0.85, base), 2)


def format_index_explanations_markdown(explanations: list[dict[str, Any]]) -> str:
    lines = ["### Why are the major indices behaving this way?", ""]
    for ex in explanations:
        lines.append(
            f"**{ex['index']} ({ex.get('name')})** — "
            f"today {fmt_num(ex.get('day_change_pct'), 2)}%, "
            f"52w momentum {fmt_num(ex.get('momentum_52w'), 1)}"
        )
        for claim in ex.get("claims") or []:
            lines.append(f"- {claim}")
        lines.append(
            support_line(
                ", ".join(ex.get("support") or []),
                ex.get("confidence"),
            )
        )
        lines.append("")
    lines.append(note("Rule-based links, not predictions. Daily moves are noisy."))
    return "\n".join(lines)
