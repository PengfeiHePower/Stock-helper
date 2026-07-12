from __future__ import annotations

from typing import Any

from stock_helper.analysis.risk_levels import allocation_for_regime
from stock_helper.config import load_yaml


def _cfg() -> dict[str, Any]:
    return load_yaml("strategy.yaml")


def build_position_sizing(
    snapshot: dict[str, Any],
    allocation: dict[str, Any],
    *,
    style_rotation: dict[str, Any] | None = None,
    risk_level: str | None = None,
) -> dict[str, Any]:
    """④ Position Sizing — how much per holding (model portfolio, not personalized)."""
    cfg = _cfg()
    ps = cfg.get("position_sizing") or {}
    level = risk_level or allocation.get("risk_level") or cfg.get("default_risk_level", "L2")
    regime = (snapshot.get("regime") or {}).get("regime", "recovery")

    regime_alloc = allocation_for_regime(regime, level)
    equity_budget = float(allocation.get("weights", {}).get("us_equity", regime_alloc["equity_budget_pct"]))
    max_single = float(regime_alloc.get("max_single_stock_pct", 8))

    core_etf = ps.get("core_etf", "SPY")
    growth_etf = ps.get("growth_tilt_etf", "QQQ")
    style = snapshot.get("strategy", {}).get("style_rotation") if False else None

    style_data = style_rotation or {}
    growth_tilt = (style_data.get("tilts") or {}).get("growth", 0)

    growth_pct = min(15.0, max(0.0, 5.0 + growth_tilt * 2.5)) if growth_tilt > 0 else 0.0
    core_pct = round(equity_budget - growth_pct, 1)

    holdings: list[dict[str, Any]] = [
        {
            "ticker": core_etf,
            "weight_pct": core_pct,
            "role": "core",
            "role_zh": "核心",
            "rationale": "Broad US equity beta",
        },
    ]
    if growth_pct > 0:
        holdings.append(
            {
                "ticker": growth_etf,
                "weight_pct": growth_pct,
                "role": "growth_tilt",
                "role_zh": "成长倾斜",
                "rationale": "Growth leadership overlay",
            }
        )

    consensus = (snapshot.get("consensus") or {}).get("consensus") or {}
    lens_map = snapshot.get("lens_map") or {}
    factor_rows = {r["ticker"]: r for r in (snapshot.get("factor_rows") or []) if r.get("ticker")}
    min_score = float(ps.get("min_lens_score", 65))
    max_names = int(ps.get("max_satellite_names", 5))
    min_lenses = int(ps.get("consensus_min_lenses", 2))

    satellite_candidates: list[tuple[str, float]] = []
    for ticker, lenses in consensus.items():
        if len(lenses) < min_lenses:
            continue
        best = (lens_map.get(ticker) or [{}])[0]
        score = best.get("score") or factor_rows.get(ticker, {}).get("composite") or 0
        if score >= min_score:
            satellite_candidates.append((ticker, float(score)))

    satellite_candidates.sort(key=lambda x: -x[1])
    satellite_budget = max(0.0, equity_budget - core_pct - growth_pct)
    if satellite_candidates and satellite_budget > 0:
        per_name = min(max_single, round(satellite_budget / min(len(satellite_candidates), max_names), 1))
        used = 0.0
        for ticker, score in satellite_candidates[:max_names]:
            if used + per_name > satellite_budget + 0.1:
                break
            holdings.append(
                {
                    "ticker": ticker,
                    "weight_pct": per_name,
                    "role": "satellite",
                    "role_zh": "卫星",
                    "rationale": f"Multi-lens consensus (score {score})",
                    "lens_score": score,
                }
            )
            used += per_name
        core_pct = round(max(0.0, core_pct - used), 1)
        holdings[0]["weight_pct"] = core_pct

    non_equity = allocation.get("rows") or []
    for row in non_equity:
        if row.get("asset") == "us_equity":
            continue
        proxy = row.get("proxy")
        if proxy and row.get("weight_pct", 0) > 0:
            holdings.append(
                {
                    "ticker": proxy,
                    "weight_pct": row["weight_pct"],
                    "role": row.get("asset", "other"),
                    "role_zh": row.get("label_zh", row.get("label", "")),
                    "rationale": row.get("label", ""),
                }
            )

    total = round(sum(h["weight_pct"] for h in holdings), 1)

    return {
        "risk_level": level,
        "equity_budget_pct": equity_budget,
        "max_single_stock_pct": max_single,
        "holdings": holdings,
        "total_weight_pct": total,
        "method": "core-satellite + consensus caps",
        "note": "Illustrative model portfolio — not personalized to your holdings.",
        "note_zh": "示范组合，未针对您的实际持仓个性化。",
    }
