from __future__ import annotations

from typing import Any

from stock_helper.analysis.macro_series import MacroSeriesClient
from stock_helper.config import load_yaml


def _macro_cfg() -> dict[str, Any]:
    return load_yaml("macro_series.yaml")


def _yoy_from_levels(values: list[dict], months_back: int = 12) -> float | None:
    if len(values) < months_back + 1:
        return None
    latest = values[-1]["value"]
    prior = values[-1 - months_back]["value"]
    if prior == 0:
        return None
    return round(100.0 * (latest - prior) / prior, 2)


def _trend(values: list[dict], periods: int = 3) -> float | None:
    if len(values) < periods:
        return None
    recent = [v["value"] for v in values[-periods:]]
    return round(recent[-1] - recent[0], 3)


def build_macro_dashboard() -> dict[str, Any]:
    """Extended FRED panel for inflation / growth / policy / risk dimensions."""
    cfg = _macro_cfg()
    series_map = cfg.get("series") or {}
    limit = int(cfg.get("history_months", 18)) + 2

    client = MacroSeriesClient(series_ids=series_map)
    raw = client.fetch_all(limit=limit)

    latest: dict[str, float | None] = {}
    series_out: dict[str, list[dict]] = {}
    evidence: list[dict[str, Any]] = []

    for label, rows in raw.items():
        series_out[label] = rows
        if rows:
            latest[label] = rows[-1]["value"]
            evidence.append(
                {
                    "id": label,
                    "value": rows[-1]["value"],
                    "date": rows[-1]["date"],
                    "source": "FRED",
                }
            )

    cpi_yoy = _yoy_from_levels(series_out.get("cpi") or [], 12)
    ppi_yoy = _yoy_from_levels(series_out.get("ppi") or [], 12)
    unrate_chg = _trend(series_out.get("unemployment") or [], 3)

    dimensions = {
        "inflation": _classify_inflation(cpi_yoy, ppi_yoy, latest.get("wti_oil"), latest.get("breakeven_5y")),
        "growth": _classify_growth(unrate_chg, latest.get("industrial_production"), series_out.get("gdp") or []),
        "policy": _classify_policy(latest.get("fed_funds"), latest.get("two_year_yield"), latest.get("yield_curve_spread")),
        "risk": _classify_risk(latest.get("vix"), latest.get("hy_spread"), latest.get("dollar_index")),
    }

    composite = _composite_regime(dimensions)

    return {
        "latest": latest,
        "series": series_out,
        "derived": {
            "cpi_yoy_pct": cpi_yoy,
            "ppi_yoy_pct": ppi_yoy,
            "unemployment_3m_change": unrate_chg,
        },
        "dimensions": dimensions,
        "composite_regime": composite,
        "evidence": evidence,
    }


def _classify_inflation(
    cpi_yoy: float | None,
    ppi_yoy: float | None,
    oil: float | None,
    breakeven: float | None,
) -> dict[str, Any]:
    score = 0.0
    if cpi_yoy is not None:
        if cpi_yoy >= 4.0:
            score += 2
        elif cpi_yoy >= 2.5:
            score += 1
        else:
            score -= 1
    if breakeven is not None and breakeven >= 2.5:
        score += 1
    if oil is not None and oil >= 85:
        score += 0.5

    if score >= 2:
        label = "elevated"
    elif score >= 0.5:
        label = "moderate"
    else:
        label = "cooling"
    return {
        "label": label,
        "score": score,
        "evidence": {"cpi_yoy_pct": cpi_yoy, "ppi_yoy_pct": ppi_yoy, "wti_oil": oil, "breakeven_5y": breakeven},
    }


def _classify_growth(
    unrate_chg: float | None,
    indpro: float | None,
    gdp_series: list[dict],
) -> dict[str, Any]:
    score = 0.0
    if unrate_chg is not None:
        if unrate_chg >= 0.3:
            score -= 2
        elif unrate_chg <= -0.2:
            score += 1
    gdp_trend = _trend(gdp_series, 2) if gdp_series else None
    if gdp_trend is not None and gdp_trend > 0:
        score += 1

    if score <= -1.5:
        label = "slowing"
    elif score >= 1:
        label = "firm"
    else:
        label = "mixed"
    return {
        "label": label,
        "score": score,
        "evidence": {
            "unemployment_3m_change": unrate_chg,
            "industrial_production": indpro,
            "gdp_trend": gdp_trend,
        },
    }


def _classify_policy(
    fed_funds: float | None,
    two_year: float | None,
    curve: float | None,
) -> dict[str, Any]:
    score = 0.0
    if fed_funds is not None:
        if fed_funds >= 4.5:
            score += 2
        elif fed_funds >= 3.0:
            score += 1
        else:
            score -= 1
    if curve is not None and curve < 0:
        score += 1

    if score >= 2:
        label = "restrictive"
    elif score >= 0.5:
        label = "neutral_tight"
    else:
        label = "accommodative"
    return {
        "label": label,
        "score": score,
        "evidence": {
            "fed_funds": fed_funds,
            "two_year_yield": two_year,
            "yield_curve_spread": curve,
        },
    }


def _classify_risk(
    vix: float | None,
    hy_spread: float | None,
    dollar: float | None,
) -> dict[str, Any]:
    score = 0.0
    if vix is not None:
        if vix >= 28:
            score += 2
        elif vix >= 20:
            score += 1
        else:
            score -= 0.5
    if hy_spread is not None and hy_spread >= 5.0:
        score += 1

    if score >= 2:
        label = "elevated"
    elif score >= 0.5:
        label = "moderate"
    else:
        label = "calm"
    return {
        "label": label,
        "score": score,
        "evidence": {"vix": vix, "hy_spread": hy_spread, "dollar_index": dollar},
    }


def _composite_regime(dimensions: dict[str, dict]) -> dict[str, Any]:
    growth = dimensions["growth"]["label"]
    policy = dimensions["policy"]["label"]
    risk = dimensions["risk"]["label"]
    inflation = dimensions["inflation"]["label"]

    if growth == "slowing" and (policy in ("restrictive", "neutral_tight") or risk == "elevated"):
        regime = "slowdown"
    elif risk == "elevated" and growth == "slowing":
        regime = "recession_risk"
    elif growth == "firm" and risk == "calm":
        regime = "expansion"
    else:
        regime = "recovery"

    return {
        "regime": regime,
        "summary": f"inflation={inflation}, growth={growth}, policy={policy}, risk={risk}",
    }
