from __future__ import annotations

from typing import Any

from stock_helper.analysis.factors import build_sector_rotation
from stock_helper.cio.reasoning_chain import (
    build_investment_decision,
    stars,
    stars_numeric,
    trend_label,
    valuation_label,
)
from stock_helper.config import load_yaml


def _cfg() -> dict[str, Any]:
    return load_yaml("cio.yaml")


def _topic_hits(snapshot: dict[str, Any]) -> dict[str, int]:
    sentiment = snapshot.get("sentiment") or {}
    reasoning = snapshot.get("reasoning") or {}
    hits: dict[str, int] = {}

    for row in sentiment.get("top_topics") or []:
        hits[row.get("topic", "")] = row.get("count", 0)

    nb = reasoning.get("narrative_block") or {}
    dom = nb.get("dominant_topic")
    if dom:
        hits[dom] = hits.get(dom, 0) + 10

    for kw_set in (sentiment.get("voices") or []):
        for h in kw_set.get("sample_headlines") or []:
            text = (h or "").lower()
            for tid, theme in (_cfg().get("themes") or {}).items():
                for kw in theme.get("keywords") or []:
                    if kw.lower() in text:
                        hits[tid] = hits.get(tid, 0) + 1
    return hits


def _etf_momentum(etf: str, sector_rows: list[dict]) -> float | None:
    for r in sector_rows:
        if r.get("etf") == etf:
            return r.get("momentum_score")
    return None


def build_theme_rotation(snapshot: dict[str, Any], *, refresh: bool = False) -> dict[str, Any]:
    """Layer 2 — Theme Rotation Engine."""
    cfg = _cfg()
    regime = snapshot.get("regime") or {}
    reasoning = snapshot.get("reasoning") or {}
    structure = snapshot.get("structure") or {}
    ind = regime.get("indicators") or {}

    topic_hits = _topic_hits(snapshot)
    sector_rows = build_sector_rotation(refresh=refresh)
    etf_mom = {r["etf"]: r.get("momentum_score") or 50 for r in sector_rows}

    cpi = float(ind.get("cpi_yoy_pct") or 3)
    vix = float(ind.get("vix") or 18)
    breadth_narrow = (structure.get("breadth") or {}).get("signal") in ("narrow", "narrow_rally")

    winning: list[dict[str, Any]] = []
    for tid, theme in (cfg.get("themes") or {}).items():
        score = 50.0
        evidence: list[str] = []

        for topic in theme.get("narrative_topics") or []:
            if topic_hits.get(topic, 0) > 0:
                score += min(15, topic_hits[topic] * 2)
                evidence.append(f"Narrative: {topic} ({topic_hits[topic]} hits)")

        moms = []
        for etf in theme.get("momentum_etfs") or []:
            m = etf_mom.get(etf.upper())
            if m is not None:
                moms.append(m)
        if moms:
            avg_mom = sum(moms) / len(moms)
            score += (avg_mom - 50) * 0.4
            evidence.append(f"Momentum ETFs avg {avg_mom:.0f}")

        if tid == "ai_infrastructure" and (reasoning.get("narrative_block") or {}).get("dominant_topic") == "ai":
            score += 12
            evidence.append("Dominant AI narrative")

        macro_support = "High" if score >= 65 else "Moderate" if score >= 50 else "Low"
        val_score = 55 + (vix - 18) * 2 + (10 if breadth_narrow else 0)
        if cpi >= 3.5:
            val_score += 8

        decision = "Overweight" if score >= 68 else "Neutral" if score >= 52 else "Underweight"
        counter = []
        if val_score >= 65:
            counter.append("Valuation expensive")
        if cpi >= 3.5 and tid in ("ai_infrastructure", "healthcare_innovation"):
            counter.append("Rates/inflation headwind")

        winning.append(
            {
                "id": tid,
                "name": theme.get("name"),
                "name_zh": theme.get("name_zh"),
                "rating": stars(score),
                "rating_score": stars_numeric(score),
                "score": round(score, 1),
                "momentum": trend_label(score - 50),
                "macro_support": macro_support,
                "valuation": valuation_label(val_score),
                "catalyst": theme.get("catalyst_default"),
                "risk": theme.get("risk_default"),
                "horizon": theme.get("horizon"),
                "decision": decision,
                "reasoning": build_investment_decision(
                    entity_type="theme",
                    entity_id=tid,
                    entity_name=theme.get("name", tid),
                    evidence=evidence or [f"Theme baseline score {score:.0f}"],
                    hypothesis=f"{theme.get('name')} remains a leading capital flow theme.",
                    counter_evidence=counter,
                    decision=decision,
                    confidence=min(0.95, score / 100),
                    monitor=["Next earnings guidance", "Capex commentary"],
                ),
            }
        )

    winning.sort(key=lambda x: x["score"], reverse=True)

    weak: list[dict[str, Any]] = []
    for wid, wt in (cfg.get("weak_themes") or {}).items():
        etf = (wt.get("etf") or "").upper()
        mom = etf_mom.get(etf, 45)
        weak.append(
            {
                "id": wid,
                "name": wt.get("name"),
                "name_zh": wt.get("name_zh"),
                "reason": wt.get("reason"),
                "momentum_score": mom,
            }
        )

    return {
        "winning_themes": winning,
        "weak_themes": weak,
        "dominant_theme": winning[0] if winning else None,
    }
