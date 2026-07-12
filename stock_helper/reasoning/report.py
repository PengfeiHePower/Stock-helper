from __future__ import annotations

from typing import Any

from stock_helper.analysis.formatting import fmt_num, note


def format_reasoning_markdown(reasoning: dict[str, Any], *, compact: bool = False) -> str:
    """Thesis-first market reasoning — evidence-derived (Phase 3)."""
    thesis = reasoning.get("thesis") or {}
    conflict = reasoning.get("conflict") or {}
    lines = [
        "## Today's Thesis",
        "",
    ]
    lines.extend(_format_thesis_status(reasoning.get("thesis_status") or {}))
    lines.extend(
        [
            "**Market thesis:**",
            thesis.get("headline", "Thesis unavailable."),
            "",
            "**Evidence:**",
        ]
    )
    for e in (thesis.get("evidence") or [])[:8]:
        lines.append(f"- {e.get('metric')}: {e.get('value')} ({e.get('source', 'data')})")
    lines.append("")
    lines.append("**Inference:**")
    for inf in thesis.get("inferences") or []:
        lines.append(f"- {inf.get('text')}")
    lines.append("")
    analog = thesis.get("historical_similarity") or {}
    if analog:
        lines.append(
            f"**Confidence:** {fmt_num(thesis.get('overall_confidence'), 2)} · "
            f"**Historical analog:** {analog.get('period', '—')} — {analog.get('similarity', '')}"
        )
        if analog.get("difference"):
            lines.append(f"  Difference today: {analog['difference']}")
    lines.append("")

    lines.extend(_format_hypotheses(reasoning.get("hypotheses") or {}))
    lines.extend(_format_hypothesis_diff(reasoning.get("hypothesis_diff") or {}))
    lines.extend(_format_drivers(reasoning.get("top_drivers") or []))
    lines.extend(_format_what_changed(reasoning))
    lines.extend(_format_conflict(conflict, reasoning.get("layer_signals") or {}))
    lines.extend(_format_counter(reasoning.get("counter_evidence") or {}))

    if not compact:
        lines.extend(_format_causal_graph(reasoning.get("evidence_graph") or {}))
        lines.extend(_format_structure_why(reasoning.get("structure_why") or []))
        lines.extend(_format_breadth_scores(reasoning.get("breadth_deep") or {}))
        lines.extend(_format_temporal(reasoning.get("temporal_views") or {}))
        lines.extend(_format_narratives(reasoning.get("narrative_block") or {}))
        lines.extend(_format_uncertainties(reasoning.get("uncertainties") or []))
        lines.extend(_format_scenarios(reasoning.get("scenarios") or []))

    lines.append(note("Evidence-derived reasoning — not investment advice."))
    return "\n".join(lines)


def _format_thesis_status(status: dict[str, Any]) -> list[str]:
    if not status:
        return []
    st = status.get("status", "HOLD")
    icon = {"HOLD": "✓", "WEAKEN": "↓", "INVALIDATED": "✗"}.get(st, "•")
    lines = [
        f"**Thesis status: {st}** {icon}",
    ]
    for r in status.get("reasons") or []:
        lines.append(f"- {r}")
    if status.get("confidence_delta") is not None:
        lines.append(
            f"- Confidence: {fmt_num(status.get('prior_confidence'), 2)} → "
            f"{fmt_num(status.get('current_confidence'), 2)} "
            f"({status['confidence_delta']:+.2f})"
        )
    if status.get("likelihood_delta") is not None:
        lines.append(
            f"- Selected hypothesis likelihood Δ {status['likelihood_delta']:+.2f} "
            f"(now {fmt_num(status.get('selected_likelihood'), 2)})"
        )
    lines.append("")
    return lines


def _format_hypothesis_diff(diff: dict[str, Any]) -> list[str]:
    if not diff.get("has_prior"):
        return [
            "## Hypothesis Evolution",
            "",
            diff.get("summary", "No prior snapshot."),
            "",
        ]
    lines = [
        "## Hypothesis Evolution",
        "",
        diff.get("summary", ""),
        "",
    ]
    for d in diff.get("diffs") or []:
        if d.get("direction") == "new":
            continue
        arrow = {"up": "↑", "down": "↓", "flat": "→"}.get(d.get("direction"), "→")
        lines.append(
            f"- **{d.get('label')}** {arrow} "
            f"{fmt_num(d.get('prior_likelihood'), 2)} → {fmt_num(d.get('current_likelihood'), 2)} "
            f"({d.get('delta'):+.2f})"
        )
        for s in d.get("newly_supported") or []:
            lines.append(f"  + {s}")
        for c in d.get("newly_contradicted") or []:
            lines.append(f"  − {c}")
    lines.append("")
    return lines


def _format_hypotheses(hyp: dict[str, Any]) -> list[str]:
    if not hyp.get("hypotheses"):
        return []
    lines = [
        "## Competing Hypotheses",
        "",
        f"**Observation:** {hyp.get('observation', '—')}",
        "",
        "| Hypothesis | Likelihood | Supporting | Contradicting |",
        "|------------|------------|------------|---------------|",
    ]
    for h in hyp.get("hypotheses") or []:
        sup = "; ".join((h.get("supporting_evidence") or [])[:2]) or "—"
        con = "; ".join((h.get("contradicting_evidence") or [])[:2]) or "—"
        lines.append(
            f"| {h.get('label', h.get('id'))} | {fmt_num(h.get('likelihood'), 2)} | {sup[:60]} | {con[:60]} |"
        )
    sel = hyp.get("selected") or {}
    lines.append("")
    lines.append(
        f"**Selected explanation:** {sel.get('label', '—')} "
        f"(confidence {fmt_num(sel.get('confidence'), 2)})"
    )
    lines.append("")
    return lines


def _format_drivers(drivers: list[dict[str, Any]]) -> list[str]:
    lines = ["## Top Drivers", ""]
    for d in drivers:
        lines.append(
            f"{d.get('rank', '•')}. **{d.get('label')}** — importance {fmt_num(d.get('importance'), 2)} · "
            f"{d.get('direction', 'neutral')}"
        )
        bd = d.get("importance_breakdown") or {}
        if bd:
            parts = [f"{k} {fmt_num(v, 2)}" for k, v in bd.items() if k != "note" and isinstance(v, (int, float))]
            if parts:
                lines.append(f"   Why: {' · '.join(parts)}")
            if bd.get("note"):
                lines.append(f"   {bd['note']}")
        elif d.get("detail"):
            lines.append(f"   {d['detail']}")
    lines.append("")
    return lines


def _format_what_changed(reasoning: dict[str, Any]) -> list[str]:
    lines = ["## What Changed", ""]
    changed = [c for c in (reasoning.get("what_changed") or []) if c.get("changed")]
    if not changed:
        lines.append("No material changes vs prior snapshot.")
    else:
        for c in changed[:6]:
            if c.get("field") == "baseline":
                lines.append(f"- {c.get('note', '')}")
                continue
            label = c.get("label", c.get("field"))
            lines.append(f"- **{label}:** {c.get('prior', '—')} → {c.get('current', '—')}")
            if c.get("note"):
                lines.append(f"  {c['note']}")
    lines.append("")
    return lines


def _format_conflict(
    conflict: dict[str, Any],
    layer_signals: dict[str, dict[str, Any]],
) -> list[str]:
    res = conflict.get("resolution") or {}
    lines = [
        "## Conflict Analysis (system)",
        "",
        f"**Level:** {conflict.get('level', '—')} · "
        f"**Overall confidence:** {fmt_num(conflict.get('overall_confidence'), 2)}",
        "",
        conflict.get("summary", ""),
        "",
    ]
    for ld in conflict.get("layer_detail") or []:
        because = ", ".join(ld.get("because") or [])
        lines.append(
            f"- **{ld.get('layer', '').title()}** {ld.get('direction')} "
            f"because {because} (conf {fmt_num(ld.get('confidence'), 2)})"
        )
    lines.append("")
    if res:
        lines.append(f"**Resolution — trust {res.get('trusted_layer', '—')}:** {res.get('statement', '')}")
        if res.get("unless"):
            lines.append(f"  Unless: {res['unless']}")
    lines.append("")
    lines.append("| Layer | Signal | Confidence |")
    lines.append("|-------|--------|------------|")
    for layer, sig in layer_signals.items():
        lines.append(
            f"| {layer.title()} | {sig.get('direction', '—')} | {fmt_num(sig.get('confidence'), 2)} |"
        )
    lines.append("")
    return lines


def _format_counter(counter: dict[str, Any]) -> list[str]:
    lines = ["## Counter Evidence", ""]
    if counter.get("bullish_because"):
        lines.append("**Bullish because:**")
        for b in counter["bullish_because"]:
            lines.append(f"- {b}")
        lines.append("")
    if counter.get("bearish_because"):
        lines.append("**However:**")
        for b in counter["bearish_because"]:
            lines.append(f"- {b}")
        lines.append("")
    if counter.get("therefore"):
        lines.append(f"**Therefore:** {counter['therefore']}")
        lines.append(f"Adjusted confidence: {fmt_num(counter.get('adjusted_confidence'), 2)}")
    lines.append("")
    return lines


def _format_causal_graph(graph: dict[str, Any]) -> list[str]:
    chain = graph.get("primary_chain")
    if not chain:
        return []
    return [
        "## Causal Evidence Graph",
        "",
        "```",
        chain.strip(),
        "```",
        "",
        f"Chain confidence: {fmt_num(graph.get('confidence'), 2)}",
        "",
    ]


def _format_structure_why(chains: list[dict[str, Any]]) -> list[str]:
    if not chains:
        return []
    lines = ["## Structure — Why?", ""]
    for c in chains:
        steps = " → ".join(s["label"] for s in c.get("steps") or [])
        lines.append(f"- **{c.get('observation')}:** {steps}")
    lines.append("")
    return lines


def _format_breadth_scores(bd: dict[str, Any]) -> list[str]:
    if not bd:
        return []
    rets = bd.get("returns") or {}
    lines = [
        "## Breadth Scores",
        "",
        f"| Metric | Score |",
        f"|--------|-------|",
        f"| Participation | {fmt_num(bd.get('participation_score'), 1)}/100 |",
        f"| Leadership | {fmt_num(bd.get('leadership_score'), 2)} |",
        f"| Breadth (sectors) | {fmt_num(bd.get('breadth_score'), 2)} |",
        f"| Sector participation | {fmt_num(bd.get('sector_participation_pct'), 0)}% beating SPY |",
        "",
        f"SPY {rets.get('SPY', '—')}% · RSP {rets.get('RSP', '—')}% · "
        f"IWM {rets.get('IWM', '—')}% · QQQ {rets.get('QQQ', '—')}%",
        "",
        bd.get("interpretation", ""),
        "",
    ]
    return lines


def _format_temporal(views: dict[str, dict[str, Any]]) -> list[str]:
    if not views:
        return []
    lines = ["## Temporal Views", "", "| Factor | Short | Medium | Long |", "|--------|-------|--------|------|"]
    for factor, v in list(views.items())[:6]:
        lines.append(
            f"| {factor} | {v.get('short_term', {}).get('direction', '—')} | "
            f"{v.get('medium_term', {}).get('direction', '—')} | "
            f"{v.get('long_term', {}).get('direction', '—')} |"
        )
    lines.append("")
    return lines


def _format_narratives(block: dict[str, Any]) -> list[str]:
    if not block:
        return []
    shift = block.get("narrative_shift") or {}
    lines = [
        "## Narrative Evolution",
        "",
        f"**Mood:** {block.get('overall_mood', '—')} · "
        f"**Shift:** {'Yes' if shift.get('changed') else 'No'} — {shift.get('note', '')}",
        "",
    ]
    for n in (block.get("narratives") or [])[:3]:
        lines.append(f"**{n.get('topic', '').upper()}** — stage: {n.get('stage', '—')}")
        if n.get("stage_shift"):
            lines.append(f"  Shift: {n['stage_shift']}")
        lines.append(f"  Path: {n.get('evolution_path', '—')}")
        lines.append(f"  {n.get('narrative')}")
        lines.append(f"  Implication: {n.get('implication')}")
        lines.append("")
    return lines


def _format_uncertainties(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return []
    lines = ["## Key Uncertainties", ""]
    for u in items:
        breaker = " [thesis-breaker]" if u.get("thesis_breaker") else ""
        lines.append(f"- **{u.get('label')}**{breaker}: {u.get('note')}")
        if u.get("watch"):
            lines.append(f"  Watch: {u['watch']}")
    lines.append("")
    return lines


def _format_scenarios(scenarios: list[dict[str, Any]]) -> list[str]:
    if not scenarios:
        return []
    lines = ["## Scenario Engine", ""]
    for s in scenarios[:4]:
        path = " → ".join(s.get("path") or [])
        lines.append(f"**{s.get('trigger')}** — probability ~{s.get('probability_pct', '—')}%")
        lines.append(f"- Path: {path}")
        lines.append(f"- Thesis impact: {s.get('thesis_impact', '—')}")
        lines.append(f"- Watch: {s.get('watch')}")
        lines.append("")
    return lines
