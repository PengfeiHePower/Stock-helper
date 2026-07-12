from __future__ import annotations

from datetime import date
from typing import Any

from stock_helper.reasoning.breadth_deep import analyze_breadth_deep
from stock_helper.reasoning.causality import build_causality_chains
from stock_helper.reasoning.change_detector import build_change_summary, detect_changes
from stock_helper.reasoning.conflict import detect_conflict
from stock_helper.reasoning.counter_evidence import build_counter_evidence
from stock_helper.reasoning.driver_ranker import rank_top_drivers
from stock_helper.reasoning.evidence_graph import build_evidence_graph
from stock_helper.reasoning.hypotheses import generate_hypotheses
from stock_helper.reasoning.hypothesis_tracker import compute_thesis_status, track_hypothesis_evolution
from stock_helper.reasoning.narrative_topics import analyze_narrative_topics
from stock_helper.reasoning.scenarios import build_scenarios
from stock_helper.reasoning.signals import compute_layer_signals, confidence_breakdown, refine_sub_regime
from stock_helper.reasoning.snapshot import get_prior_reasoning_snapshot
from stock_helper.reasoning.structure_why import build_structure_why_chains
from stock_helper.reasoning.temporal import build_temporal_views
from stock_helper.reasoning.thesis import build_thesis
from stock_helper.reasoning.uncertainties import build_uncertainties


def build_market_reasoning(
    snapshot: dict[str, Any],
    *,
    refresh: bool = False,
    use_llm: bool | None = None,
) -> dict[str, Any]:
    """
    Market Reasoning Agent — evidence-derived thesis + hypothesis testing.
    """
    regime = snapshot.get("regime") or {}
    structure = snapshot.get("structure") or {}
    sentiment = snapshot.get("sentiment") or {}

    prior = get_prior_reasoning_snapshot()
    prior_topics = (prior or {}).get("narrative_block", {}).get("ranking")
    prior_narratives = (prior or {}).get("narrative_block", {}).get("narratives")

    breadth_deep = analyze_breadth_deep(structure, refresh=refresh)
    narrative_block = analyze_narrative_topics(
        sentiment, prior_topics=prior_topics, prior_narratives=prior_narratives
    )
    narratives = narrative_block.get("narratives") or []

    layer_signals = compute_layer_signals(
        regime,
        structure,
        sentiment,
        breadth_deep=breadth_deep,
        narratives=narratives,
    )
    conflict = detect_conflict(layer_signals, regime=regime, sentiment=sentiment)
    counter_evidence = build_counter_evidence(layer_signals, conflict, breadth_deep)

    top_drivers = rank_top_drivers(
        regime,
        structure,
        sentiment,
        breadth_deep=breadth_deep,
        narratives=narratives,
    )
    regime_detail = refine_sub_regime(regime, structure)
    change_summary = build_change_summary(
        regime, structure, sentiment, conflict, top_drivers, narratives
    )
    what_changed = detect_changes(change_summary, prior)

    causality_chains = build_causality_chains(regime, structure, breadth_deep)
    evidence_graph = build_evidence_graph(causality_chains, regime, structure, breadth_deep)
    structure_why = build_structure_why_chains(regime, structure, breadth_deep)
    hypotheses = generate_hypotheses(regime, structure, breadth_deep, sentiment)
    hypothesis_diff = track_hypothesis_evolution(hypotheses, prior)
    temporal_views = build_temporal_views(regime, top_drivers, narrative_block)

    thesis = build_thesis(
        regime=regime,
        regime_detail=regime_detail,
        structure=structure,
        layer_signals=layer_signals,
        conflict=conflict,
        top_drivers=top_drivers,
        counter_evidence=counter_evidence,
        breadth_deep=breadth_deep,
        hypotheses=hypotheses,
        causal_graph=evidence_graph,
        narrative_block=narrative_block,
        use_llm=use_llm,
    )
    uncertainties = build_uncertainties(regime, narrative_block, thesis)
    thesis_status = compute_thesis_status(
        hypotheses, thesis, prior, hypothesis_diff, uncertainties=uncertainties
    )
    scenarios = build_scenarios(regime, sentiment, narrative_block, thesis=thesis)

    return {
        "as_of_date": date.today().isoformat(),
        "thesis": thesis,
        "thesis_status": thesis_status,
        "hypothesis_diff": hypothesis_diff,
        "top_drivers": top_drivers,
        "what_changed": what_changed,
        "change_summary": change_summary,
        "layer_signals": layer_signals,
        "conflict": conflict,
        "confidence_breakdown": confidence_breakdown(layer_signals),
        "regime_detail": regime_detail,
        "breadth_deep": breadth_deep,
        "causality_chains": causality_chains,
        "evidence_graph": evidence_graph,
        "structure_why": structure_why,
        "hypotheses": hypotheses,
        "temporal_views": temporal_views,
        "narrative_block": narrative_block,
        "counter_evidence": counter_evidence,
        "uncertainties": uncertainties,
        "scenarios": scenarios,
    }
