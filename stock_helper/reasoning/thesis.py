from __future__ import annotations

from typing import Any

from stock_helper.reasoning.thesis_derivation import derive_thesis


def build_thesis(
    *,
    regime: dict[str, Any],
    regime_detail: dict[str, Any],
    structure: dict[str, Any],
    layer_signals: dict[str, dict[str, Any]],
    conflict: dict[str, Any],
    top_drivers: list[dict[str, Any]],
    counter_evidence: dict[str, Any],
    breadth_deep: dict[str, Any] | None = None,
    hypotheses: dict[str, Any] | None = None,
    causal_graph: dict[str, Any] | None = None,
    narrative_block: dict[str, Any] | None = None,
    use_llm: bool | None = None,
) -> dict[str, Any]:
    """Evidence → Inference → Thesis. LLM disabled by default (Phase 3)."""
    derived = derive_thesis(
        regime=regime,
        regime_detail=regime_detail,
        structure=structure,
        breadth_deep=breadth_deep,
        hypotheses=hypotheses or {},
        causal_graph=causal_graph or {},
        conflict=conflict,
        counter_evidence=counter_evidence,
    )
    # Keep headline as derived; LLM polish optional and off by default
    _ = use_llm, narrative_block, top_drivers, layer_signals
    return derived
