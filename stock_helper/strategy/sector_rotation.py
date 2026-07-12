from __future__ import annotations

from typing import Any

from stock_helper.analysis.factors import build_sector_rotation
from stock_helper.config import load_yaml


def _cfg() -> dict[str, Any]:
    return load_yaml("strategy.yaml")


def _sector_meta(etf: str) -> dict[str, str]:
    labels = (_cfg().get("sector_labels") or {}).get(etf.upper()) or {}
    return {
        "etf": etf.upper(),
        "name": labels.get("name", etf),
        "name_zh": labels.get("name_zh", etf),
    }


def build_sector_rotation_strategy(
    snapshot: dict[str, Any],
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    """② Sector Rotation — overweight / underweight vs benchmark."""
    structure = snapshot.get("structure") or {}
    reasoning = snapshot.get("reasoning") or {}

    rotation_rows = build_sector_rotation(refresh=refresh)
    if not rotation_rows:
        leaders = structure.get("sector_leaders") or []
        laggards = structure.get("sector_laggards") or []
        rotation_rows = [
            {**r, "momentum_score": r.get("momentum_score"), "rank": i + 1}
            for i, r in enumerate(leaders + laggards)
        ]

    overweight: list[dict[str, Any]] = []
    underweight: list[dict[str, Any]] = []
    neutral: list[dict[str, Any]] = []

    for i, row in enumerate(rotation_rows):
        etf = row.get("etf", "")
        meta = _sector_meta(etf)
        entry = {
            **meta,
            "momentum_score": row.get("momentum_score"),
            "vs_spy": row.get("vs_spy"),
            "rank": row.get("rank", i + 1),
        }
        if i < 2:
            entry["stance"] = "overweight"
            overweight.append(entry)
        elif i >= len(rotation_rows) - 2:
            entry["stance"] = "underweight"
            underweight.append(entry)
        else:
            entry["stance"] = "neutral"
            neutral.append(entry)

    narrative = (reasoning.get("narrative_topics") or {}).get("dominant_topic", "")
    chain: list[str] = []
    regime = (snapshot.get("regime") or {}).get("regime", "")
    if regime:
        chain.append(f"Regime: {regime.replace('_', ' ')}")
    if narrative:
        chain.append(f"Dominant narrative: {narrative}")
        if narrative.lower() in ("ai", "tech", "technology"):
            chain.append("Growth / liquidity leadership → favor Technology (XLK)")
    if overweight:
        chain.append(f"Overweight: {', '.join(r['name'] for r in overweight)}")
    if underweight:
        chain.append(f"Underweight: {', '.join(r['name'] for r in underweight)}")

    return {
        "overweight": overweight,
        "underweight": underweight,
        "neutral": neutral[:4],
        "reasoning_chain": chain,
        "horizon": "tactical",
        "tactical_note": "Sector tilts are 1–3 month tactical overlays on strategic allocation.",
    }
