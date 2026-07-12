from __future__ import annotations

from typing import Any

from stock_helper.config import load_yaml
from stock_helper.reasoning.signals import confidence_breakdown

_LAYER_DRIVERS: dict[str, list[str]] = {
    "macro": ["growth", "liquidity", "credit"],
    "sentiment": ["tariff", "policy", "rates_headlines"],
    "breadth": ["participation", "concentration"],
    "structure": ["qqq_spy", "sector_rotation"],
}


def detect_conflict(
    layer_signals: dict[str, dict[str, Any]],
    *,
    regime: dict[str, Any] | None = None,
    sentiment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = load_yaml("reasoning.yaml").get("conflict") or {}
    high_thresh = int(cfg.get("high_disagreement", 2))
    mod_thresh = int(cfg.get("moderate_disagreement", 1))

    bullish = [k for k, v in layer_signals.items() if v.get("direction") == "bullish"]
    bearish = [k for k, v in layer_signals.items() if v.get("direction") == "bearish"]
    neutral = [k for k, v in layer_signals.items() if v.get("direction") == "neutral"]

    disagreement = min(len(bullish), len(bearish))
    if len(bullish) >= 2 and len(bearish) >= 2:
        level = "high"
    elif len(bullish) >= 1 and len(bearish) >= 1 and disagreement >= high_thresh:
        level = "high"
    elif len(bullish) >= 1 and len(bearish) >= 1:
        level = "moderate"
    elif disagreement >= mod_thresh:
        level = "moderate"
    else:
        level = "low"

    layer_detail = _layer_conflict_detail(layer_signals, regime, sentiment)
    resolution = _resolve_conflict(layer_signals, layer_detail, regime, level)

    summary = _conflict_summary(level, bullish, bearish, layer_signals)
    outcome = {
        "high": "often choppy — rallies can fade without breadth confirmation",
        "moderate": "mixed — direction depends on which layer dominates next",
        "low": "aligned — higher conviction when layers agree",
    }[level]

    conf = confidence_breakdown(layer_signals)
    if level in ("high", "moderate"):
        conf["overall"] = round(conf["overall"] * 0.85, 2)

    return {
        "level": level,
        "bullish_layers": bullish,
        "bearish_layers": bearish,
        "neutral_layers": neutral,
        "layer_detail": layer_detail,
        "resolution": resolution,
        "summary": summary,
        "historical_outcome": outcome,
        "overall_confidence": conf["overall"],
        "confidence_breakdown": conf,
    }


def _layer_conflict_detail(
    layer_signals: dict[str, dict[str, Any]],
    regime: dict[str, Any] | None,
    sentiment: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    dims = (regime or {}).get("dimension_labels") or {}
    topics = {t["topic"]: t["count"] for t in ((sentiment or {}).get("top_topics") or [])}
    details = []

    for layer, sig in layer_signals.items():
        because: list[str] = []
        if layer == "macro":
            if dims.get("growth") == "firm":
                because.append("Growth firm")
            if dims.get("risk") in ("calm", "moderate"):
                because.append("Liquidity/credit benign")
            if dims.get("inflation") == "elevated":
                because.append("Inflation elevated")
        elif layer == "sentiment":
            if topics.get("tariff", 0) >= 2:
                because.append("Tariff headlines")
            if topics.get("rates", 0) >= 3:
                because.append("Rates/policy news")
            if topics.get("ai", 0) >= 10 and sig.get("direction") != "bearish":
                because.append("AI optimism in press")
        elif layer == "breadth":
            because.append(sig.get("reason", "Breadth read"))
        else:
            because.append(sig.get("reason", layer))

        details.append(
            {
                "layer": layer,
                "direction": sig.get("direction"),
                "confidence": sig.get("confidence"),
                "because": because or [sig.get("reason", "—")],
            }
        )
    return details


def _resolve_conflict(
    layer_signals: dict[str, dict[str, Any]],
    layer_detail: list[dict[str, Any]],
    regime: dict[str, Any] | None,
    level: str,
) -> dict[str, Any]:
    """Which evidence should we trust more?"""
    if level == "low":
        dominant = layer_detail[0] if layer_detail else {}
        return {
            "trusted_layer": dominant.get("layer", "macro"),
            "trust_reason": "Layers aligned — no resolution needed.",
            "unless": None,
            "statement": "Signals agree — higher conviction on dominant layer.",
        }

    macro = layer_signals.get("macro", {})
    sent = layer_signals.get("sentiment", {})
    macro_conf = macro.get("confidence", 0.5)
    sent_conf = sent.get("confidence", 0.5)
    inflation = (regime or {}).get("dimension_labels", {}).get("inflation")

    if macro.get("direction") == "bullish" and sent.get("direction") == "bearish":
        trusted = "macro" if macro_conf >= sent_conf else "sentiment"
        return {
            "trusted_layer": trusted,
            "trust_reason": (
                "Macro historically dominates slow-moving allocation decisions."
                if trusted == "macro"
                else "Headline risk dominates near-term price action."
            ),
            "distrusted_layer": "sentiment" if trusted == "macro" else "macro",
            "unless": "Inflation surprise or tariff escalation" if inflation == "elevated" else "Major policy shock",
            "statement": (
                "Trust macro over sentiment unless inflation surprises or tariff risk escalates."
                if trusted == "macro"
                else "Trust near-term sentiment until macro data confirms."
            ),
        }

    # Default: higher confidence layer
    ranked = sorted(layer_detail, key=lambda x: x.get("confidence") or 0, reverse=True)
    trusted = ranked[0]["layer"] if ranked else "macro"
    distrusted = ranked[-1]["layer"] if len(ranked) > 1 else None
    return {
        "trusted_layer": trusted,
        "trust_reason": f"Highest layer confidence ({ranked[0].get('confidence')}).",
        "distrusted_layer": distrusted,
        "unless": "Cross-layer confirmation arrives",
        "statement": f"Weight {trusted} signal more until conflicting layer confirms.",
    }


def _conflict_summary(
    level: str,
    bullish: list[str],
    bearish: list[str],
    layer_signals: dict[str, dict[str, Any]],
) -> str:
    if level == "low":
        dominant = bullish or bearish or ["neutral"]
        d = dominant[0]
        return f"Layers largely agree — {d} read from {', '.join(dominant)}."
    bull_reason = layer_signals.get(bullish[0], {}).get("reason", "") if bullish else ""
    bear_reason = layer_signals.get(bearish[0], {}).get("reason", "") if bearish else ""
    if bull_reason and bear_reason:
        return f"{bull_reason.split('.')[0]}, but {bear_reason.split('.')[0].lower()}."
    return "Cross-layer signals disagree — treat headline index moves with caution."
