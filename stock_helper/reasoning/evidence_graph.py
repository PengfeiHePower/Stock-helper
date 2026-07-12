from __future__ import annotations

from typing import Any


def build_causal_evidence_graph(
    regime: dict[str, Any],
    structure: dict[str, Any],
    breadth_deep: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Full causal chain: Inflation → Fed → Yield → Valuation → QQQ → NVDA."""
    ind = regime.get("indicators") or {}
    dims = regime.get("dimension_labels") or {}
    gspread = (structure.get("growth_vs_broad") or {}).get("daily_spread_pct")

    chain = [
        {"id": "inflation", "label": f"Inflation {dims.get('inflation', '—')}", "value": ind.get("cpi_yoy_pct")},
        {"id": "fed", "label": f"Fed stance: {dims.get('policy', '—')}", "value": ind.get("fed_funds")},
        {"id": "yield", "label": f"10Y yield {ind.get('ten_year_yield', '—')}%", "value": ind.get("ten_year_yield")},
        {"id": "valuation", "label": "Growth valuation / duration pressure"},
        {"id": "qqq", "label": f"QQQ vs SPY {gspread}%", "value": gspread},
        {"id": "semis", "label": "Semiconductor / AI complex"},
        {"id": "nvda", "label": "NVDA (Mag7 proxy)"},
    ]

    edges = [{"from": chain[i]["id"], "to": chain[i + 1]["id"], "relation": "leads_to"} for i in range(len(chain) - 1)]

    ascii_tree = _render_chain(chain)
    return {
        "chain": chain,
        "edges": edges,
        "primary_chain": ascii_tree,
        "confidence": 0.74 if ind.get("ten_year_yield") and gspread is not None else 0.55,
    }


def build_evidence_graph(
    causality_chains: list[dict[str, Any]],
    regime: dict[str, Any],
    structure: dict[str, Any],
    breadth_deep: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Nodes and edges + merged causal chain."""
    causal = build_causal_evidence_graph(regime, structure, breadth_deep)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = list(causal.get("edges") or [])

    def _add_node(node_id: str, label: str, layer: str, value: Any = None) -> None:
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "label": label, "layer": layer, "value": value}

    dims = regime.get("dimension_labels") or {}
    ind = regime.get("indicators") or {}

    for step in causal.get("chain") or []:
        _add_node(step["id"], step["label"], "causal", step.get("value"))

    _add_node("macro", "Macro environment", "macro", regime.get("regime"))
    for dim in ("inflation", "growth", "policy", "risk"):
        _add_node(dim, f"{dim.title()}: {dims.get(dim, '—')}", "macro", dims.get(dim))

    leader = (breadth_deep or {}).get("sector_day_leaders") or []
    if leader:
        _add_node("sector", f"Sector: {leader[0]['etf']}", "sector", leader[0].get("day_change_pct"))

    for sym in ("SPY", "QQQ", "DIA"):
        idx = (structure.get("indices") or {}).get(sym, {})
        if idx:
            _add_node(sym.lower(), sym, "index", idx.get("day_change_pct"))

    for chain in causality_chains:
        steps = chain.get("steps") or []
        for i in range(len(steps) - 1):
            a, b = steps[i], steps[i + 1]
            _add_node(a["node"], a["label"], "chain", a.get("value"))
            _add_node(b["node"], b["label"], "chain", b.get("value"))
            edges.append({"from": a["node"], "to": b["node"], "relation": "leads_to"})

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "primary_chain": causal.get("primary_chain"),
        "primary_chain_id": causality_chains[0]["id"] if causality_chains else "inflation_to_nvda",
        "causal_chain": causal.get("chain"),
        "confidence": causal.get("confidence"),
    }


def _render_chain(chain: list[dict[str, Any]]) -> str:
    lines = []
    for i, step in enumerate(chain):
        prefix = "      " if i > 0 else ""
        arrow = "   │\n   ▼\n" if i < len(chain) - 1 else ""
        val = f" ({step['value']})" if step.get("value") is not None else ""
        lines.append(f"{prefix}{step['label']}{val}")
        if arrow and i == 0:
            lines.append("   │\n   ▼")
        elif arrow:
            lines.append("   │\n   ▼")
    return "\n".join(lines[: min(13, len(lines) * 2)])
