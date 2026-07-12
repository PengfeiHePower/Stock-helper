from __future__ import annotations

from typing import Any

from stock_helper.analysis.risk_levels import default_risk_level
from stock_helper.cio.reasoning_chain import build_investment_decision
from stock_helper.config import load_yaml


def _cfg() -> dict[str, Any]:
    return load_yaml("cio.yaml")


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return weights
    return {k: round(v * 100.0 / total, 1) for k, v in weights.items()}


def build_portfolio(
    snapshot: dict[str, Any],
    regime_layer: dict[str, Any],
    theme_layer: dict[str, Any],
    stock_layer: dict[str, Any],
    *,
    risk_level: str | None = None,
) -> dict[str, Any]:
    """Layer 5 — Portfolio construction (US only)."""
    cfg = _cfg()
    regime = snapshot.get("regime") or {}
    reasoning = snapshot.get("reasoning") or {}
    regime_key = regime.get("regime", "recovery")
    level = risk_level or cfg.get("default_risk_level") or default_risk_level()

    base = dict((cfg.get("allocation") or {}).get(regime_key) or (cfg.get("allocation") or {}).get("recovery") or {})
    weights = {k: float(v) for k, v in base.items() if k != "international"}

    tilt = (cfg.get("risk_level_tilt") or {}).get(level) or {}
    eq_mult = float(tilt.get("equity_mult", 1.0))
    if "us_equity" in weights:
        old = weights["us_equity"]
        new = round(old * eq_mult, 1)
        diff = new - old
        weights["us_equity"] = new
        weights["cash"] = max(0, weights.get("cash", 0) - diff * 0.6)
        weights["bonds"] = max(0, weights.get("bonds", 0) - diff * 0.4)

    conflict = (reasoning.get("conflict") or {}).get("level")
    if conflict == "high":
        weights["cash"] = weights.get("cash", 0) + 5
        weights["us_equity"] = max(0, weights.get("us_equity", 0) - 5)
    weights = _normalize(weights)

    strategic = [
        {
            "asset": k,
            "weight_pct": v,
            "label": _asset_label(k),
            "proxy": _asset_proxy(k),
        }
        for k, v in sorted(weights.items(), key=lambda x: -x[1])
    ]

    active_tilts: list[dict[str, Any]] = []
    for t in (theme_layer.get("winning_themes") or [])[:4]:
        if t.get("decision") == "Overweight":
            tilt_pct = round(min(5, (t["score"] - 60) * 0.15), 1)
            if tilt_pct > 0:
                active_tilts.append(
                    {
                        "target": t["name"],
                        "target_zh": t.get("name_zh"),
                        "tilt_pct": tilt_pct,
                        "direction": "+",
                    }
                )
    for w in (theme_layer.get("weak_themes") or [])[:2]:
        active_tilts.append(
            {
                "target": w["name"],
                "target_zh": w.get("name_zh"),
                "tilt_pct": 2.0,
                "direction": "-",
            }
        )

    etfs: list[str] = ["SPY"]
    theme_etf_map = cfg.get("theme_etfs") or {}
    for t in (theme_layer.get("winning_themes") or [])[:3]:
        for etf in theme_etf_map.get(t["id"], []):
            if etf not in etfs:
                etfs.append(etf)
    for e in ("TLT", "GLD"):
        if e not in etfs:
            etfs.append(e)

    stock_sleeve = [
        {"ticker": s["ticker"], "weight_pct": _sleeve_weight(i), "rating": s["rating"]}
        for i, s in enumerate((stock_layer.get("top_picks") or [])[:6])
    ]

    reasoning_dec = build_investment_decision(
        entity_type="portfolio",
        entity_id="model",
        entity_name="US Model Portfolio",
        evidence=[f"Regime {regime_key}", f"Risk {level}", f"Top theme {theme_layer.get('dominant_theme', {}).get('name', '—')}"],
        hypothesis="Strategic US allocation with tactical theme tilts.",
        counter_evidence=["Valuation", "Concentration risk"] if conflict == "high" else ["Macro uncertainty"],
        decision="Implement via ETF core + selective stock sleeve",
        confidence=0.65,
        monitor=["Rebalance on 5% drift", "Earnings season"],
    )

    return {
        "risk_level": level,
        "strategic_allocation": strategic,
        "weights": weights,
        "active_tilts": active_tilts,
        "etf_implementation": etfs,
        "stock_sleeve": stock_sleeve,
        "reasoning": reasoning_dec,
    }


def _asset_label(k: str) -> str:
    return {
        "us_equity": "US Equity",
        "bonds": "Bonds",
        "gold": "Gold",
        "cash": "Cash",
    }.get(k, k)


def _asset_proxy(k: str) -> str | None:
    return {"us_equity": "SPY", "bonds": "TLT", "gold": "GLD"}.get(k)


def _sleeve_weight(rank: int) -> float:
    return [3.0, 2.5, 2.0, 2.0, 1.5, 1.5][rank] if rank < 6 else 1.0
