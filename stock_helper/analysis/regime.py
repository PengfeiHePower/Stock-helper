from __future__ import annotations

import json
from datetime import date
from typing import Any

from stock_helper.analysis.macro_dashboard import build_macro_dashboard
from stock_helper.storage.db import RegimeSnapshot, get_session


def classify_regime(dashboard: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Four-dimensional macro regime + composite label.
    Rule-based — not ML. See docs/ANALYSIS.md.
    """
    dashboard = dashboard or build_macro_dashboard()
    dimensions = dashboard.get("dimensions") or {}
    composite = dashboard.get("composite_regime") or {}
    derived = dashboard.get("derived") or {}
    latest = dashboard.get("latest") or {}

    regime = composite.get("regime", "recovery")
    dim_scores = {k: v.get("label") for k, v in dimensions.items()}

    return {
        "regime": regime,
        "confidence": _confidence(dimensions),
        "dimensions": dimensions,
        "dimension_labels": dim_scores,
        "composite_summary": composite.get("summary"),
        "scores": {k: v.get("score", 0) for k, v in dimensions.items()},
        "indicators": {
            "yield_curve_spread": latest.get("yield_curve_spread"),
            "vix": latest.get("vix"),
            "unemployment_3m_change": derived.get("unemployment_3m_change"),
            "fed_funds": latest.get("fed_funds"),
            "ten_year_yield": latest.get("ten_year_yield"),
            "two_year_yield": latest.get("two_year_yield"),
            "cpi_yoy_pct": derived.get("cpi_yoy_pct"),
            "ppi_yoy_pct": derived.get("ppi_yoy_pct"),
            "dollar_index": latest.get("dollar_index"),
            "wti_oil": latest.get("wti_oil"),
            "hy_spread": latest.get("hy_spread"),
        },
        "dashboard": dashboard,
        "evidence": dashboard.get("evidence") or [],
    }


def _confidence(dimensions: dict[str, dict]) -> float:
    scores = [abs(v.get("score", 0)) for v in dimensions.values()]
    if not scores:
        return 0.5
    return round(min(0.95, 0.4 + sum(scores) / (len(scores) * 4)), 2)


def save_regime_snapshot(result: dict[str, Any], as_of: str | None = None) -> None:
    as_of_date = as_of or date.today().isoformat()
    session = get_session()
    session.add(
        RegimeSnapshot(
            as_of_date=as_of_date,
            regime=result["regime"],
            scores_json=json.dumps(
                {
                    "dimensions": result.get("dimension_labels"),
                    "scores": result.get("scores"),
                }
            ),
            indicators_json=json.dumps(
                {
                    "indicators": result.get("indicators"),
                    "confidence": result.get("confidence"),
                    "composite_summary": result.get("composite_summary"),
                }
            ),
        )
    )
    session.commit()
    session.close()


def get_latest_regime() -> dict[str, Any] | None:
    session = get_session()
    row = session.query(RegimeSnapshot).order_by(RegimeSnapshot.id.desc()).first()
    session.close()
    if not row:
        return None
    extra = json.loads(row.indicators_json or "{}")
    scores = json.loads(row.scores_json or "{}")
    return {
        "as_of_date": row.as_of_date,
        "regime": row.regime,
        "dimension_labels": scores.get("dimensions"),
        **extra,
    }
