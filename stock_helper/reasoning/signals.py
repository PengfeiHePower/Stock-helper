from __future__ import annotations

from typing import Any

from stock_helper.config import load_yaml


def _cfg() -> dict[str, Any]:
    return load_yaml("reasoning.yaml")


def refine_sub_regime(regime: dict[str, Any], structure: dict[str, Any]) -> dict[str, Any]:
    """Finer regime tag beyond expansion/slowdown/etc."""
    dims = regime.get("dimension_labels") or {}
    composite = regime.get("regime", "recovery")
    breadth_signal = (structure.get("breadth") or {}).get("signal", "mixed")
    cfg = _cfg().get("sub_regime") or {}

    tags: list[str] = []
    for tag, rules in cfg.items():
        ok = True
        if "growth_labels" in rules and dims.get("growth") not in rules["growth_labels"]:
            ok = False
        if "policy_labels" in rules and dims.get("policy") not in rules["policy_labels"]:
            ok = False
        if "inflation_labels" in rules and dims.get("inflation") not in rules["inflation_labels"]:
            ok = False
        if "risk_labels" in rules and dims.get("risk") not in rules["risk_labels"]:
            ok = False
        if "breadth_signals" in rules and breadth_signal not in rules["breadth_signals"]:
            ok = False
        if ok:
            tags.append(tag)

    primary = tags[0] if tags else composite.replace("_", " ")
    return {
        "composite": composite,
        "tags": tags,
        "primary": primary,
        "label": _sub_regime_label(primary),
    }


def _sub_regime_label(tag: str) -> str:
    return {
        "late_cycle": "Late-cycle expansion",
        "selective_risk_on": "Selective risk-on",
        "liquidity_neutral": "Liquidity-neutral",
        "expansion": "Expansion",
        "slowdown": "Slowdown",
        "recession_risk": "Recession risk",
        "recovery": "Recovery",
    }.get(tag, tag.replace("_", " ").title())


def _macro_direction_score(regime: dict[str, Any]) -> tuple[str, float, str]:
    dims = regime.get("dimensions") or {}
    scores = regime.get("scores") or {}
    labels = regime.get("dimension_labels") or {}

    total = sum(float(scores.get(k, 0)) for k in ("growth", "policy", "risk", "inflation"))
    growth = labels.get("growth")
    policy = labels.get("policy")
    risk = labels.get("risk")
    inflation = labels.get("inflation")

    if growth == "firm" and risk in ("calm", "moderate") and policy != "restrictive":
        direction = "bullish"
        reason = "Resilient growth with contained risk supports risk assets."
    elif growth == "slowing" or risk == "elevated":
        direction = "bearish"
        reason = "Growth slowing or elevated risk raises downside macro pressure."
    elif inflation == "elevated" and policy in ("restrictive", "neutral_tight"):
        direction = "bearish"
        reason = "Inflation above comfort zone with tight policy caps valuation expansion."
    elif total >= float((_cfg().get("signals") or {}).get("macro_bullish_min_score", 1.5)):
        direction = "bullish"
        reason = "Macro composite skews supportive for equities."
    elif total <= float((_cfg().get("signals") or {}).get("macro_bearish_max_score", -1.0)):
        direction = "bearish"
        reason = "Macro composite skews defensive."
    else:
        direction = "neutral"
        reason = "Macro readings are mixed — no single dominant macro force."

    dim_conf = regime.get("confidence") or 0.55
    return direction, round(min(0.92, dim_conf), 2), reason


def _breadth_direction(
    structure: dict[str, Any],
    breadth_deep: dict[str, Any] | None,
) -> tuple[str, float, str]:
    signal = (structure.get("breadth") or {}).get("signal", "mixed")
    spread = (structure.get("breadth") or {}).get("daily_spread_pct")
    participation = (breadth_deep or {}).get("participation_score")

    if signal == "narrow_rally" or (participation is not None and participation < 35):
        return (
            "bearish",
            0.74,
            "Breadth is weak — cap-weight gains outpace equal-weight participation.",
        )
    if signal == "broad_participation" or (participation is not None and participation >= 65):
        return (
            "bullish",
            0.76,
            "Broad participation supports the rally — gains are not mega-cap only.",
        )
    if spread is not None and spread <= -1.5:
        return (
            "bearish",
            0.62,
            f"RSP lagging SPY ({spread}%) — narrow leadership today.",
        )
    if spread is not None and spread >= 0.8:
        return (
            "bullish",
            0.64,
            f"Equal-weight keeping pace ({spread}%) — healthier breadth.",
        )
    return "neutral", 0.55, "No extreme breadth signal — participation looks mixed."


def _sentiment_direction(
    sentiment: dict[str, Any],
    narratives: list[dict[str, Any]] | None = None,
) -> tuple[str, float, str]:
    mood = sentiment.get("mood", "neutral")
    topics = sentiment.get("top_topics") or []
    top = topics[0]["topic"] if topics else None

    if mood == "cautious":
        return "bearish", 0.58, "News flow skews cautious (rates/tariff/policy risk)."
    if mood == "optimistic_thematic" and top == "ai":
        return "bullish", 0.62, "AI narrative dominates headlines — thematic optimism."
    if mood == "neutral":
        return "neutral", 0.52, "News mood is neutral — no dominant fear or euphoria."

    dominant = (narratives or [{}])[0].get("topic") if narratives else top
    return "neutral", 0.55, f"Sentiment mixed around {dominant or 'headlines'}."


def _structure_direction(structure: dict[str, Any]) -> tuple[str, float, str]:
    spread = (structure.get("growth_vs_broad") or {}).get("daily_spread_pct")
    if spread is not None and spread < -0.15:
        return (
            "bearish",
            0.68,
            f"QQQ underperforming SPY ({spread}%) — growth/tech lagging the broad tape.",
        )
    if spread is not None and spread > 0.15:
        return (
            "bullish",
            0.66,
            f"QQQ leading SPY ({spread}%) — growth leadership intact.",
        )
    return "neutral", 0.54, "Growth vs broad market is in line today."


def compute_layer_signals(
    regime: dict[str, Any],
    structure: dict[str, Any],
    sentiment: dict[str, Any],
    *,
    breadth_deep: dict[str, Any] | None = None,
    narratives: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    macro_d, macro_c, macro_r = _macro_direction_score(regime)
    breadth_d, breadth_c, breadth_r = _breadth_direction(structure, breadth_deep)
    sent_d, sent_c, sent_r = _sentiment_direction(sentiment, narratives)
    struct_d, struct_c, struct_r = _structure_direction(structure)

    return {
        "macro": {"direction": macro_d, "confidence": macro_c, "reason": macro_r},
        "breadth": {"direction": breadth_d, "confidence": breadth_c, "reason": breadth_r},
        "sentiment": {"direction": sent_d, "confidence": sent_c, "reason": sent_r},
        "structure": {"direction": struct_d, "confidence": struct_c, "reason": struct_r},
    }


def confidence_breakdown(layer_signals: dict[str, dict[str, Any]]) -> dict[str, float]:
    breakdown = {k: v["confidence"] for k, v in layer_signals.items()}
    vals = list(breakdown.values())
    breakdown["overall"] = round(sum(vals) / len(vals), 2) if vals else 0.5
    return breakdown
