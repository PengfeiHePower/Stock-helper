from __future__ import annotations

from typing import Any

from stock_helper.analysis.factors import score_ticker_factors
from stock_helper.analysis.strategies import score_strategy_lenses
from stock_helper.cio.reasoning_chain import build_investment_decision, stars, stars_numeric, valuation_label
from stock_helper.collectors.fundamentals import load_fundamentals_map
from stock_helper.config import load_yaml
from stock_helper.watchlist import all_watchlist_tickers, get_core_tickers


def _cfg() -> dict[str, Any]:
    return load_yaml("cio.yaml")


def _industry_for_ticker(ticker: str) -> tuple[str, str]:
    for iid, ind in (_cfg().get("industries") or {}).items():
        if ticker.upper() in [t.upper() for t in ind.get("tickers") or []]:
            return iid, ind.get("name", iid)
    return "general", "General"


def build_stock_ranking(
    snapshot: dict[str, Any],
    industry_layer: dict[str, Any],
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    """Layer 4 — Stock ranking grouped by industry."""
    universe = sorted(set(get_core_tickers()) | set(all_watchlist_tickers()))
    funds = load_fundamentals_map(universe, refresh=refresh)
    lens_map = snapshot.get("lens_map") or {}
    factor_map = {r["ticker"]: r for r in (snapshot.get("factor_rows") or []) if r.get("ticker")}

    ind_scores = {i["id"]: i["score"] for i in industry_layer.get("industries") or []}

    ranked: list[dict[str, Any]] = []
    by_industry: dict[str, list[dict]] = {}

    for ticker in universe:
        data = funds.get(ticker.upper())
        if not data:
            continue
        factors = score_ticker_factors(data)
        lenses = score_strategy_lenses(ticker, data)
        f = factors.get("factors") or {}
        composite = factors.get("composite") or 50
        best_lens = lenses[0] if lenses else None
        lens_score = best_lens.get("score", 50) if best_lens else 50

        iid, iname = _industry_for_ticker(ticker)
        parent = ind_scores.get(iid, 50)
        score = composite * 0.4 + lens_score * 0.35 + parent * 0.25

        pe = (factors.get("raw") or {}).get("peTTM")
        val_label = valuation_label(75 if pe and float(pe) > 35 else 50 if pe and float(pe) > 22 else 35)

        bull = _bull_case(ticker, f, best_lens)
        bear = _bear_case(ticker, f, snapshot)
        decision = "Overweight" if score >= 72 else "Neutral" if score >= 55 else "Underweight"

        entry = {
            "ticker": ticker.upper(),
            "industry_id": iid,
            "industry_name": iname,
            "rating": stars(score),
            "rating_score": stars_numeric(score),
            "score": round(score, 1),
            "why": bull[:2],
            "quality": f.get("quality"),
            "momentum": f.get("momentum"),
            "valuation": val_label,
            "risk": "High" if (f.get("momentum") or 0) > 80 and val_label == "Expensive" else "Moderate",
            "confidence": round(min(0.95, score / 100), 2),
            "best_lens": best_lens.get("lens_id") if best_lens else None,
            "bull_case": bull,
            "bear_case": bear,
            "catalyst": bull[0] if bull else "Earnings / guidance",
            "invalidation": bear[0] if bear else "Thesis break on earnings miss",
            "decision": decision,
            "reasoning": build_investment_decision(
                entity_type="stock",
                entity_id=ticker.upper(),
                entity_name=ticker.upper(),
                evidence=[f"Composite {composite}", f"Lens {lens_score}", f"Industry parent {parent:.0f}"],
                hypothesis=bull[0] if bull else f"{ticker} fits current theme/industry stack.",
                counter_evidence=bear[:2],
                decision=decision,
                confidence=min(0.95, score / 100),
                monitor=["Next earnings", "Guidance revision"],
            ),
        }
        ranked.append(entry)
        by_industry.setdefault(iname, []).append(entry)

    ranked.sort(key=lambda x: x["score"], reverse=True)
    for lst in by_industry.values():
        lst.sort(key=lambda x: x["score"], reverse=True)

    return {
        "stocks": ranked,
        "by_industry": by_industry,
        "top_picks": ranked[:10],
    }


def _bull_case(ticker: str, factors: dict, lens: dict | None) -> list[str]:
    out = []
    if (factors.get("momentum") or 0) >= 70:
        out.append("Strong momentum / relative strength")
    if (factors.get("quality") or 0) >= 70:
        out.append("Quality earnings / balance sheet")
    if lens:
        out.append(f"{lens.get('name', lens.get('lens_id'))} lens fit")
    if ticker == "NVDA":
        out.insert(0, "AI capex / GPU demand")
    if ticker == "MU":
        out.insert(0, "HBM / memory pricing")
    if ticker in ("RTX", "LMT", "NOC", "GD"):
        out.insert(0, "Defense budget / modernization")
    if ticker in ("CRWD", "PANW", "ZS"):
        out.insert(0, "Security spend / breach cycle")
    if ticker == "LLY":
        out.insert(0, "GLP-1 / pipeline momentum")
    if ticker == "COST":
        out.insert(0, "Resilient consumer")
    return out or ["Watchlist core name"]


def _bear_case(ticker: str, factors: dict, snapshot: dict) -> list[str]:
    out = []
    pe = factors.get("value")
    if pe is not None and pe < 40:
        out.append("Stretched valuation")
    reasoning = snapshot.get("reasoning") or {}
    if (reasoning.get("conflict") or {}).get("level") == "high":
        out.append("Macro conflict / narrow breadth")
    if ticker in ("NVDA", "AMD", "MU"):
        out.append("Cycle / capex slowdown risk")
    return out or ["Macro slowdown"]
