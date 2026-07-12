from __future__ import annotations

from typing import Any

from stock_helper.config import load_yaml


def _cfg() -> dict[str, Any]:
    return load_yaml("strategy.yaml")


def _arrow(delta: int) -> str:
    if delta >= 2:
        return "↑↑"
    if delta == 1:
        return "↑"
    if delta <= -2:
        return "↓↓"
    if delta == -1:
        return "↓"
    return "→"


def build_style_rotation(snapshot: dict[str, Any]) -> dict[str, Any]:
    """③ Style Rotation — growth/value, cap size, factor tilts."""
    cfg = _cfg()
    structure = snapshot.get("structure") or {}
    reasoning = snapshot.get("reasoning") or {}
    regime = snapshot.get("regime") or {}

    styles = {
        "growth": 0,
        "value": 0,
        "large_cap": 0,
        "small_cap": 0,
        "momentum": 0,
        "quality": 0,
        "low_volatility": 0,
        "dividend": 0,
    }

    sub_regime = (reasoning.get("signals") or {}).get("sub_regime") or {}
    primary_tag = sub_regime.get("primary", "")
    sub_tilts = (cfg.get("sub_regime_style") or {}).get(primary_tag) or {}
    for k, v in sub_tilts.items():
        if k in styles:
            styles[k] += int(v)

    breadth = structure.get("breadth") or {}
    signal = breadth.get("signal", "")
    if signal in ("narrow_rally", "narrow"):
        styles["large_cap"] += 1
        styles["small_cap"] -= 2
        styles["momentum"] += 1

    gvb = structure.get("growth_vs_broad") or {}
    spread = gvb.get("daily_spread_pct")
    if spread is not None and float(spread) > 0.15:
        styles["growth"] += 2
        styles["momentum"] += 1
    elif spread is not None and float(spread) < -0.15:
        styles["value"] += 1
        styles["low_volatility"] += 1

    iwm = structure.get("small_cap") or {}
    iwm_day = iwm.get("day_change_pct")
    if iwm_day is not None and float(iwm_day) < -0.3:
        styles["small_cap"] -= 1
        styles["large_cap"] += 1

    regime_key = regime.get("regime", "recovery")
    preferred_lens = (cfg.get("regime_lens_preference") or {}).get(regime_key, "")
    lens_style_map = {
        "momentum_trend": {"momentum": 2, "growth": 1},
        "defensive_dividend": {"dividend": 2, "low_volatility": 2, "quality": 1},
        "dalio_all_weather": {"low_volatility": 2, "quality": 1},
        "bogle_core_satellite": {"quality": 1, "large_cap": 1},
        "buffett_quality": {"quality": 2, "value": 1},
    }
    for k, v in lens_style_map.get(preferred_lens, {}).items():
        styles[k] = styles.get(k, 0) + v

    rows = [
        {"style": k, "tilt": v, "arrow": _arrow(v)}
        for k, v in sorted(styles.items(), key=lambda x: -abs(x[1]))
        if v != 0
    ]

    chain = [f"Sub-regime: {sub_regime.get('label', primary_tag)}"]
    if preferred_lens:
        chain.append(f"Preferred lens anchor: {preferred_lens}")
    if signal:
        chain.append(f"Breadth: {signal}")

    return {
        "tilts": styles,
        "rows": rows,
        "preferred_lens": preferred_lens,
        "reasoning_chain": chain,
        "horizon": "tactical",
    }
