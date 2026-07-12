from __future__ import annotations

from typing import Any

from stock_helper.analysis.factors import score_ticker_factors
from stock_helper.cio.reasoning_chain import (
    build_investment_decision,
    stars,
    stars_numeric,
    trend_label,
    valuation_label,
)
from stock_helper.collectors.fundamentals import load_fundamentals_map
from stock_helper.config import load_yaml
from stock_helper.watchlist import all_watchlist_tickers, get_core_tickers


def _cfg() -> dict[str, Any]:
    return load_yaml("cio.yaml")


def build_industry_rotation(
    snapshot: dict[str, Any],
    theme_layer: dict[str, Any],
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    """Layer 3 — Industry Rotation under themes."""
    cfg = _cfg()
    theme_scores = {t["id"]: t["score"] for t in theme_layer.get("winning_themes") or []}
    factor_map = {r["ticker"]: r for r in (snapshot.get("factor_rows") or []) if r.get("ticker")}

    universe = sorted(set(get_core_tickers()) | set(all_watchlist_tickers()))
    funds = load_fundamentals_map(universe, refresh=refresh)

    industries: list[dict[str, Any]] = []
    by_theme: dict[str, list[dict]] = {}

    for iid, ind_cfg in (cfg.get("industries") or {}).items():
        theme_id = ind_cfg.get("theme", "")
        parent_score = theme_scores.get(theme_id, 50)

        tickers = [t for t in (ind_cfg.get("tickers") or []) if t in universe or t in funds]
        mom_scores = []
        for t in tickers:
            if t in factor_map:
                m = (factor_map[t].get("factors") or {}).get("momentum")
                if m is not None:
                    mom_scores.append(m)
            elif t.upper() in funds:
                m = score_ticker_factors(funds[t.upper()])["factors"].get("momentum")
                if m is not None:
                    mom_scores.append(m)

        avg_mom = sum(mom_scores) / len(mom_scores) if mom_scores else 50
        score = parent_score * 0.55 + avg_mom * 0.45
        pe_vals = []
        for t in tickers:
            raw = (factor_map.get(t) or {}).get("raw") or {}
            if raw.get("peTTM"):
                pe_vals.append(float(raw["peTTM"]))

        val_score = 60 if pe_vals and sum(pe_vals) / len(pe_vals) > 30 else 45
        decision = "Overweight" if score >= 65 else "Neutral" if score >= 50 else "Underweight"

        entry = {
            "id": iid,
            "theme_id": theme_id,
            "name": ind_cfg.get("name"),
            "name_zh": ind_cfg.get("name_zh"),
            "rating": stars(score),
            "rating_score": stars_numeric(score),
            "score": round(score, 1),
            "trend": trend_label(avg_mom - 50),
            "catalyst": _industry_catalyst(iid, theme_id),
            "valuation": valuation_label(val_score),
            "risk": _industry_risk(iid),
            "representative_stocks": tickers[:4],
            "etf": ind_cfg.get("etf"),
            "decision": decision,
            "reasoning": build_investment_decision(
                entity_type="industry",
                entity_id=iid,
                entity_name=ind_cfg.get("name", iid),
                evidence=[
                    f"Parent theme score {parent_score:.0f}",
                    f"Industry momentum {avg_mom:.0f}",
                ],
                hypothesis=f"{ind_cfg.get('name')} benefits from {theme_id.replace('_', ' ')}.",
                counter_evidence=[f"Valuation {valuation_label(val_score)}", "Cycle risk"],
                decision=decision,
                confidence=min(0.9, score / 100),
                monitor=["Sector earnings", "Pricing trends"],
            ),
        }
        industries.append(entry)
        by_theme.setdefault(theme_id, []).append(entry)

    for lst in by_theme.values():
        lst.sort(key=lambda x: x["score"], reverse=True)

    industries.sort(key=lambda x: x["score"], reverse=True)
    return {
        "industries": industries,
        "by_theme": by_theme,
        "top_industries": industries[:8],
    }


def _industry_catalyst(iid: str, theme_id: str) -> str:
    catalysts = {
        "memory": "AI server demand / HBM pricing",
        "gpu": "Hyperscaler AI capex",
        "networking": "Datacenter buildout",
        "optical": "AI cluster interconnect demand",
        "datacenter_reit": "AI capacity expansion",
        "missile": "Defense budget / NATO spend",
        "radar": "Missile defense programs",
        "satellite": "Space defense contracts",
        "defense_cyber": "DoD cyber modernization",
        "electronic_warfare": "EW systems upgrade cycle",
        "grid_equipment": "Grid modernization / AI power load",
        "nuclear_power": "Baseload + data center power",
        "factory_automation": "Reshoring automation capex",
        "cyber_software": "Enterprise zero-trust spend",
        "glp1_ecosystem": "GLP-1 demand / pipeline",
        "retail": "Resilient consumer spending",
        "travel": "Leisure demand normalization",
        "auto": "EV transition / rate sensitivity",
    }
    return catalysts.get(iid, f"{theme_id.replace('_', ' ')} tailwind")


def _industry_risk(iid: str) -> str:
    risks = {
        "memory": "Cycle peak / pricing rollover",
        "gpu": "Capex slowdown",
        "optical": "Inventory correction",
        "datacenter_reit": "Financing costs / oversupply",
        "missile": "Budget timing",
        "satellite": "Launch / program delays",
        "retail": "Consumer slowdown",
        "auto": "Rate-sensitive demand",
        "travel": "Fuel / labor cost pressure",
        "glp1_ecosystem": "Pricing / competition",
    }
    return risks.get(iid, "Macro slowdown")
