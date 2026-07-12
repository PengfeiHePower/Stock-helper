from __future__ import annotations

from typing import Any


def build_uncertainties(
    regime: dict[str, Any],
    narrative_block: dict[str, Any] | None,
    thesis: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """What we do not know — catalysts that can break the thesis."""
    ind = regime.get("indicators") or {}
    ranking = (narrative_block or {}).get("ranking") or []
    main = ranking[0] if ranking else "macro"

    items: list[dict[str, Any]] = []

    if main in ("ai", "earnings"):
        items.append(
            {
                "id": "ai_guidance",
                "label": "AI / Mag7 earnings guidance",
                "thesis_breaker": True,
                "note": "If guidance weakens, concentrated leadership thesis breaks quickly.",
                "watch": "Capex outlook, margin commentary, NVDA/MSFT reports",
            }
        )

    items.append(
        {
            "id": "next_cpi",
            "label": "Next CPI / PCE print",
            "thesis_breaker": ind.get("cpi_yoy_pct") and float(ind["cpi_yoy_pct"]) >= 3.5,
            "note": "Inflation surprise reprices Fed path and yield curve.",
            "watch": f"CPI YoY currently {ind.get('cpi_yoy_pct', '—')}%",
        }
    )

    items.append(
        {
            "id": "fed_tone",
            "label": "Fed communication tone",
            "thesis_breaker": False,
            "note": "Dovish pivot could broaden rally; hawkish surprise extends rate pressure.",
            "watch": "FOMC minutes, Powell speeches",
        }
    )

    if "tariff" in ranking:
        items.append(
            {
                "id": "tariff_escalation",
                "label": "Tariff / trade policy escalation",
                "thesis_breaker": True,
                "note": "Policy shock can override macro support quickly.",
                "watch": "Trade headlines, margin warnings",
            }
        )

    headline = (thesis or {}).get("headline", "")
    if "concentrat" in headline.lower() or "narrow" in headline.lower():
        items.append(
            {
                "id": "breadth_expansion",
                "label": "Whether breadth improves",
                "thesis_breaker": False,
                "note": "Broad participation would validate rally; continued narrowness keeps fragility.",
                "watch": "RSP vs SPY, IWM trend over 2 weeks",
            }
        )

    return items
