from __future__ import annotations

from typing import Any


def build_scenarios(
    regime: dict[str, Any],
    sentiment: dict[str, Any],
    narratives: dict[str, Any] | None = None,
    *,
    thesis: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Probability-weighted scenarios with thesis impact."""
    ind = regime.get("indicators") or {}
    main_topic = None
    if narratives:
        ranking = narratives.get("ranking") or []
        main_topic = ranking[0] if ranking else None
    if not main_topic:
        topics = sentiment.get("top_topics") or []
        main_topic = topics[0]["topic"] if topics else "macro"

    cpi = float(ind.get("cpi_yoy_pct") or 3.0)
    vix = float(ind.get("vix") or 18)

    raw: list[dict[str, Any]] = []

    raw.append(
        {
            "id": "cpi_lower",
            "trigger": "CPI below expectations",
            "path": ["CPI ↓", "Yields ↓", "QQQ ↑", "Breadth may improve"],
            "watch": "Next CPI/PCE, breakeven inflation",
            "probability": 35 if cpi >= 3.5 else 28,
            "thesis_impact": "reinforces" if "rate" in (thesis or {}).get("headline", "").lower() else "shifts_bullish",
        }
    )
    raw.append(
        {
            "id": "cpi_higher",
            "trigger": "CPI above expectations",
            "path": ["CPI ↑", "Yields ↑", "QQQ ↓", "Growth ↓"],
            "watch": "2Y yield reaction, Fed speakers",
            "probability": 42 if cpi >= 3.5 else 30,
            "thesis_impact": "invalidates" if main_topic == "ai" else "reinforces_headwinds",
        }
    )

    if main_topic in ("earnings", "ai"):
        raw.append(
            {
                "id": "earnings_beat",
                "trigger": "Mag7 / AI earnings beat & raise",
                "path": ["Earnings beat", "NVDA/MSFT lead", "QQQ ↑", "Narrow rally extends"],
                "watch": "Guidance, capex outlook",
                "probability": 28,
                "thesis_impact": "reinforces",
            }
        )
        raw.append(
            {
                "id": "earnings_miss",
                "trigger": "AI earnings disappoint / guide down",
                "path": ["Guidance cut", "Valuation reset", "QQQ ↓", "Leadership breaks"],
                "watch": "Margin/capex commentary",
                "probability": 32,
                "thesis_impact": "invalidates",
            }
        )

    raw.append(
        {
            "id": "risk_off",
            "trigger": "VIX spike / credit widening",
            "path": ["Risk-off", "HY spreads ↑", "Cyclicals ↓", "Defensives outperform"],
            "watch": f"VIX ({ind.get('vix')}), HY ({ind.get('hy_spread')})",
            "probability": 18 if vix < 18 else 30,
            "thesis_impact": "invalidates",
        }
    )

    total = sum(s["probability"] for s in raw) or 1
    for s in raw:
        s["probability_pct"] = round(100 * s["probability"] / total)
    raw.sort(key=lambda x: x["probability_pct"], reverse=True)
    return raw
