from __future__ import annotations

from datetime import date
from typing import Any

from stock_helper.config import load_yaml


def _cfg() -> dict[str, Any]:
    return load_yaml("strategy.yaml")


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return weights
    return {k: round(v * 100.0 / total, 1) for k, v in weights.items()}


def _apply_delta(
    weights: dict[str, float],
    asset: str,
    delta: float,
    *,
    from_asset: str | None = None,
) -> None:
    if asset not in weights:
        return
    weights[asset] = max(0.0, weights.get(asset, 0.0) + delta)
    if from_asset and from_asset in weights:
        weights[from_asset] = max(0.0, weights.get(from_asset, 0.0) - delta)


def build_asset_allocation(
    snapshot: dict[str, Any],
    *,
    risk_level: str | None = None,
) -> dict[str, Any]:
    """① Asset Allocation — where capital should sit across asset classes."""
    cfg = _cfg()
    regime = snapshot.get("regime") or {}
    structure = snapshot.get("structure") or {}
    reasoning = snapshot.get("reasoning") or {}
    regime_key = regime.get("regime", "recovery")
    level = risk_level or cfg.get("default_risk_level", "L2")

    templates = cfg.get("regime_templates") or {}
    base = dict(templates.get(regime_key) or templates.get("recovery") or {})

    classes_cfg = cfg.get("asset_classes") or {}
    for key, meta in classes_cfg.items():
        if not meta.get("enabled", True) and key in base:
            cut = base.pop(key, 0)
            base["cash"] = base.get("cash", 0) + cut

    weights = {k: float(v) for k, v in base.items()}

    tilt = (cfg.get("risk_level_tilt") or {}).get(level) or {}
    eq_mult = float(tilt.get("equity_mult", 1.0))
    if "us_equity" in weights:
        old_eq = weights["us_equity"]
        new_eq = round(old_eq * eq_mult, 1)
        diff = new_eq - old_eq
        weights["us_equity"] = new_eq
        if diff > 0:
            weights["cash"] = max(0.0, weights.get("cash", 0) - diff * 0.6)
            weights["bonds"] = max(0.0, weights.get("bonds", 0) - diff * 0.4)
        elif diff < 0:
            weights["cash"] = weights.get("cash", 0) - diff * 0.5
            weights["bonds"] = weights.get("bonds", 0) - diff * 0.5

    adj = cfg.get("adjustments") or {}
    conflict = (reasoning.get("conflict") or {}).get("level", "")
    ch = adj.get("conflict_high") or {}
    cm = adj.get("conflict_moderate") or {}
    nb = adj.get("narrow_breadth") or {}
    if conflict == "high":
        _apply_delta(weights, "cash", float(ch.get("cash_add", 5)))
        _apply_delta(weights, "us_equity", -float(ch.get("us_equity_cut", 5)))
    elif conflict == "moderate":
        _apply_delta(weights, "cash", float(cm.get("cash_add", 2)))
        _apply_delta(weights, "us_equity", -float(cm.get("us_equity_cut", 2)))

    ind = regime.get("indicators") or {}
    vix = ind.get("vix")
    if vix is not None:
        vix_f = float(vix)
        if vix_f >= float(adj.get("vix_stress", 28)):
            cut = float(adj.get("vix_stress_equity_cut", 8))
            add = float(adj.get("vix_stress_cash_add", 8))
            _apply_delta(weights, "us_equity", -cut)
            _apply_delta(weights, "cash", add)
        elif vix_f >= float(adj.get("vix_elevated", 20)):
            _apply_delta(weights, "cash", float(adj.get("vix_elevated_cash_add", 3)))

    breadth_signal = (structure.get("breadth") or {}).get("signal", "")
    if breadth_signal in ("narrow_rally", "narrow"):
        _apply_delta(weights, "cash", float(nb.get("cash_add", 3)))
        _apply_delta(weights, "us_equity", -float(nb.get("us_equity_cut", 3)))

    thesis_status = (reasoning.get("hypothesis_evolution") or {}).get("thesis_status", "")
    if thesis_status in ("WEAKEN", "INVALIDATED"):
        _apply_delta(weights, "cash", 4)
        _apply_delta(weights, "us_equity", -4)

    weights = _normalize_weights(weights)

    rationale: list[str] = []
    rationale.append(f"Base template: {regime_key.replace('_', ' ')} regime")
    if tilt.get("note"):
        rationale.append(f"Risk level {level}: {tilt['note']}")
    if conflict:
        rationale.append(f"Layer conflict: {conflict}")
    if vix is not None:
        rationale.append(f"VIX {vix}")
    if breadth_signal:
        rationale.append(f"Breadth signal: {breadth_signal}")

    rows = []
    for asset, pct in sorted(weights.items(), key=lambda x: -x[1]):
        meta = classes_cfg.get(asset) or {}
        rows.append(
            {
                "asset": asset,
                "label": meta.get("label", asset),
                "label_zh": meta.get("label_zh", asset),
                "weight_pct": pct,
                "proxy": meta.get("proxy"),
            }
        )

    return {
        "risk_level": level,
        "regime": regime_key,
        "weights": weights,
        "rows": rows,
        "rationale": rationale,
        "horizon": "strategic",
        "as_of_date": date.today().isoformat(),
    }
