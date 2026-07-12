from __future__ import annotations

from typing import Any


_HISTORICAL_ANALOGS: dict[str, dict[str, str]] = {
    "late_cycle": {
        "period": "2018 Q3",
        "similarity": "Firm growth + tight policy + narrow leadership",
        "difference": "Inflation higher today; credit spreads tighter",
    },
    "selective_risk_on": {
        "period": "2020 H2",
        "similarity": "Mega-cap leadership while breadth lags",
        "difference": "Fed now restrictive, not easing",
    },
    "expansion": {
        "period": "2017",
        "similarity": "Calm vol + growth firm",
        "difference": "Higher starting yields and inflation",
    },
}


def derive_thesis(
    *,
    regime: dict[str, Any],
    regime_detail: dict[str, Any],
    structure: dict[str, Any],
    breadth_deep: dict[str, Any] | None,
    hypotheses: dict[str, Any],
    causal_graph: dict[str, Any],
    conflict: dict[str, Any],
    counter_evidence: dict[str, Any],
) -> dict[str, Any]:
    """
    Evidence → Inference → Thesis (derived, not LLM-first).
    """
    evidence = _collect_evidence(regime, structure, breadth_deep)
    inferences = _build_inferences(evidence, breadth_deep, hypotheses)
    headline = _compose_headline(inferences, regime_detail, hypotheses, conflict)

    tag = regime_detail.get("primary", "mixed")
    analog = _HISTORICAL_ANALOGS.get(tag, _HISTORICAL_ANALOGS.get("expansion", {}))

    confidence = round(
        min(
            0.88,
            max(
                0.35,
                (hypotheses.get("selected") or {}).get("confidence", 0.5) * 0.5
                + (1 - {"high": 0.25, "moderate": 0.12, "low": 0.0}.get(conflict.get("level", "low"), 0))
                * 0.3
                + len(evidence) * 0.03,
            ),
        ),
        2,
    )

    return {
        "evidence": evidence,
        "inferences": inferences,
        "headline": headline,
        "regime_tag": tag,
        "regime_label": regime_detail.get("label"),
        "overall_confidence": counter_evidence.get("adjusted_confidence") or confidence,
        "derivation_confidence": confidence,
        "historical_similarity": analog,
        "primary_causal_chain": causal_graph.get("primary_chain"),
        "selected_hypothesis": hypotheses.get("selected"),
        "source": "derived",
    }


def _collect_evidence(
    regime: dict[str, Any],
    structure: dict[str, Any],
    breadth_deep: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    ind = regime.get("indicators") or {}
    bd = breadth_deep or {}
    rets = bd.get("returns") or {}
    items: list[dict[str, Any]] = []

    def _add(metric: str, value: Any, source: str = "market") -> None:
        if value is not None:
            items.append({"metric": metric, "value": value, "source": source})

    _add("mag7_avg_day_pct", bd.get("mag7_avg_day_pct"))
    _add("iwm_day_pct", rets.get("IWM"))
    _add("rsp_day_pct", rets.get("RSP"))
    _add("spy_day_pct", rets.get("SPY"))
    _add("qqq_day_pct", rets.get("QQQ"))
    _add("rsp_spy_spread", bd.get("rsp_spy_spread"))
    _add("iwm_spy_spread", bd.get("iwm_spy_spread"))
    _add("qqq_spy_spread", (structure.get("growth_vs_broad") or {}).get("daily_spread_pct"))
    _add("participation_score", bd.get("participation_score"))
    _add("leadership_score", bd.get("leadership_score"))
    _add("breadth_score", bd.get("breadth_score"))
    _add("cpi_yoy_pct", ind.get("cpi_yoy_pct"), "FRED")
    _add("ten_year_yield", ind.get("ten_year_yield"), "FRED")
    _add("hy_spread", ind.get("hy_spread"), "FRED")
    _add("vix", ind.get("vix"), "FRED")
    return items


def _build_inferences(
    evidence: list[dict[str, Any]],
    breadth_deep: dict[str, Any] | None,
    hypotheses: dict[str, Any],
) -> list[dict[str, Any]]:
    ev = {e["metric"]: e["value"] for e in evidence}
    out: list[dict[str, Any]] = []

    mag7 = ev.get("mag7_avg_day_pct")
    iwm = ev.get("iwm_day_pct")
    spy = ev.get("spy_day_pct")
    rsp_spread = ev.get("rsp_spy_spread")
    leadership = ev.get("leadership_score")

    if mag7 is not None and spy is not None and float(mag7) > float(spy) + 0.15:
        out.append(
            {
                "id": "concentrated_leadership",
                "text": "Leadership remains concentrated in mega-caps.",
                "from": ["mag7_avg_day_pct", "spy_day_pct"],
            }
        )
    if iwm is not None and spy is not None and float(iwm) < float(spy) - 0.2:
        out.append(
            {
                "id": "small_cap_lag",
                "text": "Small caps lag — risk appetite is selective, not broad.",
                "from": ["iwm_day_pct", "spy_day_pct"],
            }
        )
    if rsp_spread is not None and float(rsp_spread) < -0.1:
        out.append(
            {
                "id": "narrow_breadth",
                "text": "Equal-weight lagging cap-weight — participation is narrow.",
                "from": ["rsp_spy_spread"],
            }
        )
    if leadership is not None and float(leadership) >= 0.7:
        out.append(
            {
                "id": "high_leadership",
                "text": "Market cap concentration elevated.",
                "from": ["leadership_score"],
            }
        )

    ten_y = ev.get("ten_year_yield")
    qqq_spread = ev.get("qqq_spy_spread")
    if ten_y and float(ten_y) >= 4.0 and qqq_spread is not None and float(qqq_spread) < 0:
        out.append(
            {
                "id": "rates_press_growth",
                "text": "Elevated yields coincide with growth underperformance.",
                "from": ["ten_year_yield", "qqq_spy_spread"],
            }
        )

    sel = hypotheses.get("selected") or {}
    if sel.get("label"):
        out.append(
            {
                "id": "best_explanation",
                "text": f"Best-fit explanation: {sel['label']}.",
                "from": ["hypothesis_testing"],
            }
        )

    if not out:
        out.append(
            {"id": "mixed", "text": "No dominant inference — tape is mixed.", "from": ["evidence"]}
        )
    return out


def _compose_headline(
    inferences: list[dict[str, Any]],
    regime_detail: dict[str, Any],
    hypotheses: dict[str, Any],
    conflict: dict[str, Any],
) -> str:
    regime_label = regime_detail.get("label", "Mixed regime")
    core = [i["text"] for i in inferences if i["id"] != "best_explanation"][:2]
    core_text = " ".join(core) if core else "Market signals are mixed."

    sel = hypotheses.get("selected") or {}
    h_line = ""
    if sel.get("label") and sel.get("confidence", 0) >= 0.4:
        h_line = f" Selected explanation: {sel['label']} (confidence {sel.get('confidence')})."

    conflict_note = ""
    if conflict.get("level") in ("moderate", "high"):
        conflict_note = f" Cross-layer conflict {conflict['level']} — size conviction accordingly."

    thesis_body = ""
    if "concentrated" in core_text.lower() or "narrow" in core_text.lower():
        thesis_body = (
            "Current rally depends on mega-cap / AI earnings — "
            "elevated yields are a structural constraint, not today's primary driver."
        )
    elif sel.get("slug") == "selective_mega_cap":
        thesis_body = (
            "Investors favor liquid mega-caps while avoiding smaller names — "
            "selective risk appetite, not a broad growth selloff."
        )
    elif "rates" in core_text.lower() or "yield" in core_text.lower():
        thesis_body = "Rate pressure is the primary drag on growth valuation today."
    elif sel.get("slug") == "sector_rotation":
        thesis_body = "Sector rotation, not macro breakdown, is driving today's dispersion."
    else:
        thesis_body = "No single macro narrative dominates — stock selection over beta."

    return f"{regime_label}: {core_text}{h_line} Market thesis: {thesis_body}{conflict_note}"
