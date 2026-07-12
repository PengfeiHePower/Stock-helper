from __future__ import annotations

from typing import Any

from stock_helper.config import load_yaml


def _importance_breakdown(
    driver_id: str,
    *,
    regime: dict[str, Any],
    structure: dict[str, Any],
    sentiment: dict[str, Any],
    breadth_deep: dict[str, Any] | None,
    narratives: list[dict[str, Any]] | None,
    raw_intensity: float,
) -> dict[str, Any]:
    """Explain why a driver ranks where it does."""
    topics = sentiment.get("top_topics") or []
    news_n = max(sentiment.get("news_count") or 1, 1)
    bd = breadth_deep or {}

    if driver_id == "dominant_narrative":
        top = topics[0] if topics else {}
        share = (top.get("count") or 0) / news_n
        return {
            "mention_frequency": round(min(1.0, share * 3), 2),
            "price_sensitivity": round(min(1.0, (bd.get("leadership_score") or 0.5)), 2),
            "sector_contribution": round(min(1.0, (bd.get("tech_contribution_estimate_pct") or 30) / 80), 2),
            "cross_source_agreement": round((narratives or [{}])[0].get("confidence", 0.5), 2),
            "note": "High mention share + price linkage raises importance.",
        }

    if driver_id == "treasury_yield":
        ten_y = (regime.get("indicators") or {}).get("ten_year_yield")
        qspread = (structure.get("growth_vs_broad") or {}).get("daily_spread_pct")
        return {
            "level_elevation": round(raw_intensity, 2),
            "growth_sensitivity": round(min(1.0, abs(float(qspread or 0)) / 0.3), 2) if qspread else 0.3,
            "policy_link": 0.7 if (regime.get("dimension_labels") or {}).get("policy") in ("restrictive", "neutral_tight") else 0.4,
            "note": "Yields matter more when growth multiples are rate-sensitive.",
        }

    if driver_id == "inflation":
        cpi = (regime.get("indicators") or {}).get("cpi_yoy_pct")
        infl_mentions = next((t["count"] for t in topics if t.get("topic") == "inflation"), 0)
        return {
            "distance_from_target": round(raw_intensity, 2),
            "fed_implication": 0.75 if cpi and float(cpi) >= 3.5 else 0.45,
            "headline_attention": round(min(1.0, infl_mentions / 15), 2),
            "note": "Sticky inflation keeps Fed reaction function hawkish.",
        }

    if driver_id == "breadth":
        return {
            "rsp_spy_spread": round(min(1.0, abs(float((structure.get("breadth") or {}).get("daily_spread_pct") or 0)) / 2), 2),
            "participation_score": round((bd.get("participation_score") or 50) / 100, 2),
            "leadership_inverse": round(1 - (bd.get("leadership_score") or 0.5), 2),
            "note": "Narrow breadth raises fragility even when SPY is green.",
        }

    return {"intensity": round(raw_intensity, 2), "note": "Composite market sensitivity."}


def rank_top_drivers(
    regime: dict[str, Any],
    structure: dict[str, Any],
    sentiment: dict[str, Any],
    *,
    breadth_deep: dict[str, Any] | None = None,
    narratives: list[dict[str, Any]] | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    weights = load_yaml("reasoning.yaml").get("drivers") or {}
    ind = regime.get("indicators") or {}
    topics = sentiment.get("top_topics") or []
    news_n = max(sentiment.get("news_count") or 1, 1)

    raw: list[dict[str, Any]] = []

    ten_y = ind.get("ten_year_yield")
    if ten_y is not None:
        intensity = min(1.0, max(0.2, (float(ten_y) - 3.5) / 2.5))
        raw.append(
            {
                "id": "treasury_yield",
                "label": f"10Y Treasury at {ten_y}%",
                "importance_raw": float(weights.get("treasury_yield", 0.25)) * intensity,
                "direction": "headwind" if ten_y >= 4.0 else "tailwind" if ten_y <= 3.5 else "neutral",
                "detail": "Elevated long-end yields constrain valuation multiples, especially growth.",
                "_intensity": intensity,
            }
        )

    cpi = ind.get("cpi_yoy_pct")
    if cpi is not None:
        intensity = min(1.0, max(0.25, abs(float(cpi) - 2.0) / 3.0))
        raw.append(
            {
                "id": "inflation",
                "label": f"CPI YoY {cpi}%",
                "importance_raw": float(weights.get("inflation", 0.20)) * intensity,
                "direction": "headwind" if cpi >= 3.0 else "tailwind" if cpi <= 2.0 else "neutral",
                "detail": "Inflation path shapes Fed reaction function and rate expectations.",
                "_intensity": intensity,
            }
        )

    if topics:
        top = topics[0]
        share = top["count"] / news_n
        narrative = (narratives or [{}])[0]
        intensity = min(1.0, share * 4)
        raw.append(
            {
                "id": "dominant_narrative",
                "label": narrative.get("headline") or f"{top['topic'].upper()} narrative",
                "importance_raw": float(weights.get("dominant_narrative", 0.18)) * intensity,
                "direction": narrative.get("direction", "neutral"),
                "detail": narrative.get("implication", f"{top['count']} headlines in lookback window."),
                "_intensity": intensity,
                "topic": top["topic"],
            }
        )

    spread = (structure.get("breadth") or {}).get("daily_spread_pct")
    if spread is not None:
        intensity = min(1.0, abs(float(spread)) / 2.0)
        raw.append(
            {
                "id": "breadth",
                "label": f"RSP vs SPY {spread}%",
                "importance_raw": float(weights.get("breadth", 0.17)) * max(0.3, intensity),
                "direction": "headwind" if spread < -0.5 else "tailwind" if spread > 0.5 else "neutral",
                "detail": (breadth_deep or {}).get("interpretation")
                or (structure.get("breadth") or {}).get("interpretation", ""),
                "_intensity": intensity,
            }
        )

    gspread = (structure.get("growth_vs_broad") or {}).get("daily_spread_pct")
    if gspread is not None:
        intensity = min(1.0, abs(float(gspread)) / 0.5)
        raw.append(
            {
                "id": "growth_vs_broad",
                "label": f"QQQ vs SPY {gspread}%",
                "importance_raw": float(weights.get("growth_vs_broad", 0.12)) * max(0.25, intensity),
                "direction": "headwind" if gspread < -0.1 else "tailwind" if gspread > 0.1 else "neutral",
                "detail": "Growth/tech leadership vs broad market.",
                "_intensity": intensity,
            }
        )

    hy = ind.get("hy_spread")
    if hy is not None:
        intensity = min(1.0, max(0.2, (float(hy) - 3.5) / 2.0))
        raw.append(
            {
                "id": "credit_risk",
                "label": f"HY spread {hy}",
                "importance_raw": float(weights.get("credit_risk", 0.08)) * intensity,
                "direction": "headwind" if hy >= 4.5 else "tailwind",
                "detail": "Credit conditions affect risk appetite and equity risk premium.",
                "_intensity": intensity,
            }
        )

    raw.sort(key=lambda x: x["importance_raw"], reverse=True)
    top = raw[:limit]
    total = sum(d["importance_raw"] for d in top) or 1.0
    for i, d in enumerate(top, 1):
        d["rank"] = i
        d["importance"] = round(d["importance_raw"] / total, 2)
        d["importance_breakdown"] = _importance_breakdown(
            d["id"],
            regime=regime,
            structure=structure,
            sentiment=sentiment,
            breadth_deep=breadth_deep,
            narratives=narratives,
            raw_intensity=d.pop("_intensity", 0.5),
        )
        del d["importance_raw"]
    return top
