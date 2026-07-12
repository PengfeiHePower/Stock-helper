from __future__ import annotations

import math
from typing import Any

from stock_helper.analysis.formatting import fmt_num, note
from stock_helper.reasoning.report import (
    _format_breadth_scores,
    _format_causal_graph,
    _format_conflict,
    _format_counter,
    _format_hypothesis_diff,
    _format_narratives,
    _format_scenarios,
    _format_structure_why,
    _format_temporal,
    _format_thesis_status,
)


def _normalize_evidence_scores(hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scores = [float(h.get("likelihood") or h.get("evidence_score") or 0.1) for h in hypotheses]
    if not scores:
        return []
    max_s = max(scores)
    exps = [math.exp(s - max_s) for s in scores]
    total = sum(exps) or 1.0
    out = []
    for h, e in zip(hypotheses, exps):
        out.append({**h, "normalized_probability": round(e / total, 2)})
    return out


def format_analyst_appendix(reasoning: dict[str, Any]) -> str:
    """Technical deep dive — hypotheses, evidence keys, conflict machinery."""
    thesis = reasoning.get("thesis") or {}
    conflict = reasoning.get("conflict") or {}
    hyp_block = dict(reasoning.get("hypotheses") or {})
    if hyp_block.get("hypotheses"):
        hyp_block["hypotheses_normalized"] = _normalize_evidence_scores(hyp_block["hypotheses"])

    lines = [
        "## Deep dive — how we reached this view",
        "",
        "*(Optional reading: methodology, evidence scores, and system diagnostics.)*",
        "",
        "### Thesis tracking (system)",
        "",
    ]
    lines.extend(_format_thesis_status(reasoning.get("thesis_status") or {}))

    lines.append("**Derived headline (internal):**")
    lines.append(thesis.get("headline", "—"))
    lines.append("")
    lines.append("**Raw evidence keys:**")
    lines.append("| Metric | Value | Source |")
    lines.append("|--------|-------|--------|")
    for e in thesis.get("evidence") or []:
        lines.append(f"| {e.get('metric')} | {e.get('value')} | {e.get('source')} |")
    lines.append("")
    lines.append("**Inferences:**")
    for inf in thesis.get("inferences") or []:
        lines.append(f"- {inf.get('text')}")
    lines.append("")

    analog = thesis.get("historical_similarity") or {}
    if analog:
        lines.append(
            f"**Historical analog:** {analog.get('period')} — {analog.get('similarity')} "
            f"(diff: {analog.get('difference', '—')})"
        )
        lines.append("")

    lines.extend(_format_hypothesis_diff(reasoning.get("hypothesis_diff") or {}))

    # Renamed hypotheses section with normalized probs
    lines.append("### Competing explanations (evidence scores)")
    lines.append("")
    lines.append(
        "*Scores are independent support weights, not mutually exclusive probabilities. "
        "Normalized column uses softmax for illustration only.*"
    )
    lines.append("")
    lines.append("| Explanation | Evidence score | Normalized | Supporting | Contradicting |")
    lines.append("|-------------|----------------|------------|------------|---------------|")
    hyps = hyp_block.get("hypotheses") or []
    norm_map = {h["slug"]: h.get("normalized_probability") for h in hyp_block.get("hypotheses_normalized") or []}
    for h in hyps:
        sup = "; ".join((h.get("supporting_evidence") or [])[:2]) or "—"
        con = "; ".join((h.get("contradicting_evidence") or [])[:2]) or "—"
        lines.append(
            f"| {h.get('label')} | {fmt_num(h.get('likelihood'), 2)} | "
            f"{fmt_num(norm_map.get(h.get('slug')), 2)} | {sup[:50]} | {con[:50]} |"
        )
    lines.append("")

    lines.extend(_format_conflict(conflict, reasoning.get("layer_signals") or {}))
    lines.extend(_format_counter(reasoning.get("counter_evidence") or {}))
    lines.extend(_format_causal_graph(reasoning.get("evidence_graph") or {}))
    lines.extend(_format_structure_why(reasoning.get("structure_why") or []))
    lines.extend(_format_breadth_scores(reasoning.get("breadth_deep") or {}))
    lines.extend(_format_temporal(reasoning.get("temporal_views") or {}))
    lines.extend(_format_narratives(reasoning.get("narrative_block") or {}))
    lines.extend(_format_scenarios(reasoning.get("scenarios") or []))

    # Headlines appendix
    sentiment = reasoning.get("_sentiment_headlines")
    if sentiment:
        lines.extend(["### Headlines behind this assessment", "", sentiment, ""])

    lines.append(note("Analyst appendix — internal reasoning trace. Not investment advice."))
    return "\n".join(lines)
