from __future__ import annotations

from typing import Any


_TOPIC_NARRATIVES: dict[str, dict[str, str]] = {
    "ai": {
        "headline": "AI remains the dominant market narrative",
        "narrative": (
            "Discussion centers on AI capex and semiconductor demand, "
            "with growing debate on valuation sustainability."
        ),
        "implication": "Supports XLK/QQQ/NVDA linkage; watch for guidance disappointments.",
        "direction": "tailwind",
    },
    "rates": {
        "headline": "Fed and rates dominate the conversation",
        "narrative": "Headlines focus on Fed path, yield moves, and duration risk for equities.",
        "implication": "Rate-sensitive growth multiples under scrutiny; bond-equity correlation matters.",
        "direction": "headwind",
    },
    "inflation": {
        "headline": "Inflation data in focus",
        "narrative": "Markets weigh whether inflation is sticky enough to delay easing.",
        "implication": "CPI/PPI surprises can move yields and reprice Fed expectations quickly.",
        "direction": "headwind",
    },
    "tariff": {
        "headline": "Trade and tariff risk elevated in headlines",
        "narrative": "Policy uncertainty around trade flows into supply-chain and margin concerns.",
        "implication": "Multinationals and importers face headline risk; defensives may hold up better.",
        "direction": "headwind",
    },
    "earnings": {
        "headline": "Earnings season driving stock-specific moves",
        "narrative": "Guidance and margin commentary matter more than macro for single names.",
        "implication": "Index moves may decouple from macro — stock selection over beta.",
        "direction": "neutral",
    },
}


_TOPIC_STAGES: dict[str, list[str]] = {
    "ai": ["innovation", "capex", "profitability", "valuation"],
    "rates": ["hawkish", "pause", "easing"],
    "inflation": ["sticky", "cooling", "target"],
    "earnings": ["beats", "guidance", "margins"],
    "tariff": ["threat", "implementation", "impact"],
}


def _infer_stage(topic: str, count: int, prior_stage: str | None) -> dict[str, Any]:
    stages = _TOPIC_STAGES.get(topic, ["emerging", "dominant", "fading"])
    if count >= 50:
        idx = min(2, len(stages) - 1)
    elif count >= 15:
        idx = min(1, len(stages) - 1)
    else:
        idx = 0
    stage = stages[idx]
    shift = None
    if prior_stage and prior_stage != stage:
        shift = f"{prior_stage} → {stage}"
    return {"stage": stage, "shift": shift, "stages": stages}


def analyze_narrative_topics(
    sentiment: dict[str, Any],
    *,
    prior_topics: list[str] | None = None,
    prior_narratives: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Topic → narrative → implication, plus narrative shift detection."""
    topics = sentiment.get("top_topics") or []
    prior_topics = prior_topics or []
    prior_rank = {t: i for i, t in enumerate(prior_topics)}
    prior_stage_map = {n["topic"]: n.get("stage") for n in (prior_narratives or [])}

    narratives: list[dict[str, Any]] = []
    for i, row in enumerate(topics[:5]):
        topic = row["topic"]
        template = _TOPIC_NARRATIVES.get(topic, {})
        stage_info = _infer_stage(topic, row["count"], prior_stage_map.get(topic))
        narratives.append(
            {
                "rank": i + 1,
                "topic": topic,
                "count": row["count"],
                "headline": template.get("headline", f"{topic.title()} in headlines"),
                "narrative": template.get("narrative", f"{row['count']} mentions in lookback window."),
                "implication": template.get("implication", "Monitor for follow-through in price action."),
                "direction": template.get("direction", "neutral"),
                "confidence": round(min(0.85, 0.45 + row["count"] / 40), 2),
                "stage": stage_info["stage"],
                "stage_shift": stage_info["shift"],
                "evolution_path": " → ".join(stage_info["stages"]),
            }
        )

    current_order = [t["topic"] for t in topics[:3]]
    shift = _detect_shift(prior_rank, current_order)

    return {
        "overall_mood": sentiment.get("mood", "neutral"),
        "narratives": narratives,
        "ranking": current_order,
        "narrative_shift": shift,
        "market_sentiment": {
            "overall": sentiment.get("mood", "neutral"),
            "confidence": 0.55 if sentiment.get("mood") == "neutral" else 0.62,
        },
    }


def _detect_shift(
    prior_rank: dict[str, int],
    current_order: list[str],
) -> dict[str, Any]:
    if not prior_rank or not current_order:
        return {"changed": False, "prior_main": None, "current_main": current_order[0] if current_order else None}

    prior_main = min(prior_rank, key=prior_rank.get) if prior_rank else None
    current_main = current_order[0] if current_order else None
    changed = prior_main != current_main
    return {
        "changed": changed,
        "prior_main": prior_main,
        "current_main": current_main,
        "note": (
            f"Conversation shifted from {prior_main} toward {current_main}."
            if changed
            else f"{current_main} remains the lead narrative."
        ),
    }
