from __future__ import annotations

from typing import Any


def generate_hypotheses(
    regime: dict[str, Any],
    structure: dict[str, Any],
    breadth_deep: dict[str, Any] | None,
    sentiment: dict[str, Any],
) -> dict[str, Any]:
    """
    Abductive reasoning: multiple competing explanations for today's tape.
    Returns ranked hypotheses with supporting / contradicting evidence.
    """
    ind = regime.get("indicators") or {}
    gspread = (structure.get("growth_vs_broad") or {}).get("daily_spread_pct")
    bd = breadth_deep or {}
    topics = {t["topic"]: t["count"] for t in (sentiment.get("top_topics") or [])}

    candidates: list[dict[str, Any]] = []

    # H0: Selective mega-cap preference (often dominates when Mag7 leads, IWM lags)
    h0_support, h0_contra = [], []
    leadership = bd.get("leadership_score") or 0
    iwm_sp = bd.get("iwm_spy_spread")
    mag7_avg = bd.get("mag7_avg_day_pct")
    spy_ret = (bd.get("returns") or {}).get("SPY")

    if leadership >= 0.6:
        h0_support.append(f"Leadership score {leadership} — concentrated")
    if mag7_avg is not None and spy_ret is not None and float(mag7_avg) > float(spy_ret) + 0.15:
        h0_support.append(f"Mag7 avg {mag7_avg:+.2f}% vs SPY {spy_ret:+.2f}%")
    if iwm_sp is not None and float(iwm_sp) < -0.3:
        h0_support.append(f"IWM lagging SPY by {iwm_sp} pp")
    if gspread is not None and -0.2 < float(gspread) < 0.1:
        h0_support.append(f"QQQ only modestly behind SPY ({gspread}%) — not broad tech selloff")
    if gspread is not None and float(gspread) < -0.25:
        h0_contra.append("QQQ materially underperforming — broad growth pressure")

    if h0_support:
        candidates.append(
            _hyp(
                "H0",
                "selective_mega_cap",
                "Selective mega-cap preference",
                h0_support,
                h0_contra,
                base=0.38,
            )
        )

    # H1: Rate / duration pressure
    h1_support, h1_contra = [], []
    ten_y = ind.get("ten_year_yield")
    if ten_y and float(ten_y) >= 4.0:
        h1_support.append(f"10Y yield {ten_y}% — elevated")
    if gspread is not None and gspread < 0:
        h1_support.append(f"QQQ lagging SPY ({gspread}%)")
    policy = (regime.get("dimension_labels") or {}).get("policy")
    if policy in ("restrictive", "neutral_tight"):
        h1_support.append(f"Policy {policy}")
    hy = ind.get("hy_spread")
    if hy and float(hy) < 3.5:
        h1_contra.append(f"HY spread tight ({hy}) — credit not stressed")
    if gspread is not None and gspread > 0.1:
        h1_contra.append("QQQ leading — weak rate-pressure read")

    candidates.append(
        _hyp(
            "H1",
            "rate_pressure",
            "Rate / duration pressure on growth",
            h1_support,
            h1_contra,
            base=0.35,
        )
    )

    # H2: Sector rotation
    leaders = bd.get("sector_day_leaders") or []
    laggards = bd.get("sector_day_laggards") or []
    h2_support, h2_contra = [], []
    if leaders and leaders[0].get("etf") in ("XLF", "XLE", "XLI"):
        h2_support.append(f"{leaders[0]['etf']} leading — cyclical/value rotation")
    if leaders and leaders[0].get("etf") == "XLK":
        h2_contra.append("Tech still leading — rotation thesis weak")
    if gspread is not None and gspread < -0.1:
        h2_support.append("Growth underperforming broad")

    candidates.append(
        _hyp(
            "H2",
            "sector_rotation",
            "Sector rotation away from growth",
            h2_support,
            h2_contra,
            base=0.22,
        )
    )

    # H3: Profit taking after AI rally
    h3_support, h3_contra = [], []
    mag7_avg = bd.get("mag7_avg_day_pct")
    if mag7_avg is not None and topics.get("ai", 0) >= 20:
        h3_support.append(f"AI narrative hot ({topics.get('ai')} mentions) after strong Mag7 run")
    if (bd.get("leadership_score") or 0) >= 0.75:
        h3_support.append("Leadership still concentrated — not broad selling")
        h3_contra.append("Mag7 still outperforming — less profit-taking")
    if gspread is not None and gspread > 0:
        h3_contra.append("QQQ still leading")

    candidates.append(
        _hyp(
            "H3",
            "profit_taking",
            "Profit-taking in crowded AI trade",
            h3_support,
            h3_contra,
            base=0.18,
        )
    )

    # H4: Stock-specific / idiosyncratic
    h4_support = []
    if abs(gspread or 0) < 0.1 and (bd.get("breadth_score") or 0.5) > 0.45:
        h4_support.append("QQQ-SPY spread small; breadth mixed not extreme")
    if not h4_support:
        h4_support.append("Macro-structure link weak — single-name flows may dominate")

    candidates.append(
        _hyp(
            "H4",
            "idiosyncratic",
            "Stock-specific moves dominate index",
            h4_support,
            ["Clear macro chain present"] if len(h1_support) >= 2 else [],
            base=0.12,
        )
    )

    for h in candidates:
        h["evidence_score"] = _score_hypothesis(h)
        h["likelihood"] = h["evidence_score"]  # backward compat

    candidates.sort(key=lambda x: x["evidence_score"], reverse=True)
    selected = candidates[0]
    return {
        "observation": _primary_observation(structure, bd, gspread),
        "hypotheses": candidates,
        "selected": {
            "id": selected["id"],
            "slug": selected.get("slug"),
            "label": selected["label"],
            "confidence": selected["evidence_score"],
            "evidence_score": selected["evidence_score"],
            "because": selected["supporting_evidence"],
        },
    }


def _hyp(
    hid: str,
    slug: str,
    label: str,
    support: list[str],
    contra: list[str],
    *,
    base: float,
) -> dict[str, Any]:
    return {
        "id": hid,
        "slug": slug,
        "label": label,
        "supporting_evidence": support,
        "contradicting_evidence": contra,
        "base_prior": base,
    }


def _score_hypothesis(h: dict[str, Any]) -> float:
    base = float(h.get("base_prior", 0.2))
    support_n = len(h.get("supporting_evidence") or [])
    contra_n = len(h.get("contradicting_evidence") or [])
    score = base + support_n * 0.12 - contra_n * 0.08
    return round(max(0.08, min(0.85, score)), 2)


def _primary_observation(
    structure: dict[str, Any],
    bd: dict[str, Any],
    gspread: float | None,
) -> str:
    if (bd.get("leadership_score") or 0) >= 0.65:
        return "Mega-cap leadership with weak small-cap participation"
    if gspread is not None and gspread < -0.1:
        return f"QQQ underperforming SPY by {gspread}%"
    spy = (structure.get("indices") or {}).get("SPY", {}).get("day_change_pct")
    return f"SPY {spy}% with mixed cross-currents"
