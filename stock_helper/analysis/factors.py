from __future__ import annotations

from typing import Any

from stock_helper.collectors.fundamentals import load_fundamentals_map
from stock_helper.config import load_yaml


def _clamp(score: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, score))


def _momentum_proxy(quote: dict, metric: dict) -> float | None:
    c = quote.get("c")
    lo = metric.get("52WeekLow")
    hi = metric.get("52WeekHigh")
    if c is None or lo is None or hi is None or hi <= lo:
        return None
    return _clamp(100.0 * (float(c) - float(lo)) / (float(hi) - float(lo)))


def momentum_proxy(quote: dict, metric: dict) -> float | None:
    return _momentum_proxy(quote, metric)


def _quality_score(metric: dict) -> float | None:
    roe = metric.get("roeTTM")
    if roe is None:
        return None
    roe = float(roe)
    if roe >= 25:
        return 90.0
    if roe >= 15:
        return 75.0
    if roe >= 8:
        return 55.0
    return 35.0


def _value_score(metric: dict) -> float | None:
    pe = metric.get("peTTM") or metric.get("peBasic")
    if pe is None:
        return None
    pe = float(pe)
    if pe <= 0:
        return None
    if pe <= 18:
        return 85.0
    if pe <= 28:
        return 65.0
    if pe <= 40:
        return 45.0
    return 25.0


def _low_risk_score(metric: dict) -> float | None:
    beta = metric.get("beta")
    if beta is None:
        return None
    beta = float(beta)
    if beta <= 0.8:
        return 85.0
    if beta <= 1.1:
        return 65.0
    if beta <= 1.4:
        return 45.0
    return 30.0


def score_ticker_factors(fundamentals: dict[str, Any]) -> dict[str, Any]:
    quote = fundamentals.get("quote") or {}
    metric = fundamentals.get("metric") or {}
    factors: dict[str, float | None] = {
        "quality": _quality_score(metric),
        "value": _value_score(metric),
        "momentum": _momentum_proxy(quote, metric),
        "low_risk": _low_risk_score(metric),
    }
    valid = [v for v in factors.values() if v is not None]
    composite = round(sum(valid) / len(valid), 1) if valid else None
    return {
        "ticker": fundamentals.get("ticker"),
        "factors": factors,
        "composite": composite,
        "raw": {
            "peTTM": metric.get("peTTM"),
            "roeTTM": metric.get("roeTTM"),
            "beta": metric.get("beta"),
            "price": quote.get("c"),
        },
    }


def score_universe(tickers: list[str], refresh: bool = False) -> list[dict[str, Any]]:
    data = load_fundamentals_map(tickers, refresh=refresh)
    return [score_ticker_factors(data[t]) for t in tickers if t.upper() in data]


def relative_momentum_vs_spy(
    ticker_funds: dict[str, Any], spy_funds: dict[str, Any] | None
) -> float | None:
    t_mom = score_ticker_factors(ticker_funds)["factors"].get("momentum")
    if spy_funds is None or t_mom is None:
        return t_mom
    s_mom = score_ticker_factors(spy_funds)["factors"].get("momentum")
    if s_mom is None:
        return t_mom
    return _clamp(50.0 + (t_mom - s_mom))


def build_sector_rotation(refresh: bool = False) -> list[dict[str, Any]]:
    cfg = load_yaml("analysis.yaml")
    sectors = list((cfg.get("scope") or {}).get("sector_etfs") or [])
    market = list((cfg.get("scope") or {}).get("market_etfs") or ["SPY"])
    spy = market[0] if market else "SPY"

    data = load_fundamentals_map([spy] + sectors, refresh=refresh)
    spy_data = data.get(spy.upper())
    rows: list[dict[str, Any]] = []

    for etf in sectors:
        funds = data.get(etf.upper())
        if not funds:
            continue
        mom = relative_momentum_vs_spy(funds, spy_data)
        rows.append(
            {
                "etf": etf.upper(),
                "momentum_score": mom,
                "vs_spy": None if mom is None else round(mom - 50.0, 1),
            }
        )

    rows.sort(key=lambda r: r.get("momentum_score") or 0, reverse=True)
    for i, row in enumerate(rows, 1):
        row["rank"] = i
    return rows
