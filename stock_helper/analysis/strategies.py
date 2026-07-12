from __future__ import annotations

import json
from datetime import date
from typing import Any

from stock_helper.analysis.factors import score_ticker_factors
from stock_helper.collectors.fundamentals import load_fundamentals_map
from stock_helper.config import load_yaml
from stock_helper.storage.db import FactorScoreRecord, StrategyLensScoreRecord, get_session


def _lenses() -> dict[str, dict]:
    return load_yaml("strategies.yaml").get("lenses") or {}


def _weighted_lens_score(factors: dict[str, float | None], weights: dict[str, float]) -> float | None:
    total_w = 0.0
    total = 0.0
    key_map = {
        "quality": "quality",
        "value": "value",
        "momentum": "momentum",
        "low_risk": "low_risk",
    }
    for key, weight in weights.items():
        factor_key = key_map.get(key, key)
        val = factors.get(factor_key)
        if val is None:
            continue
        total_w += weight
        total += val * weight
    if total_w <= 0:
        return None
    return round(total / total_w, 1)


def score_strategy_lenses(
    ticker: str, fundamentals: dict[str, Any]
) -> list[dict[str, Any]]:
    factor_result = score_ticker_factors(fundamentals)
    factors = factor_result.get("factors") or {}
    results: list[dict[str, Any]] = []

    for lens_id, lens in _lenses().items():
        weights = lens.get("weights") or {}
        score = _weighted_lens_score(factors, weights)
        if score is None:
            continue
        results.append(
            {
                "lens_id": lens_id,
                "name": lens.get("name", lens_id),
                "name_zh": lens.get("name_zh", lens_id),
                "score": score,
                "horizon": lens.get("horizon"),
            }
        )
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def score_watchlist_lenses(
    tickers: list[str], refresh: bool = False
) -> dict[str, list[dict[str, Any]]]:
    data = load_fundamentals_map(tickers, refresh=refresh)
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker in tickers:
        funds = data.get(ticker.upper())
        if funds:
            out[ticker.upper()] = score_strategy_lenses(ticker, funds)
    return out


def lens_consensus(lens_scores: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Find tickers multiple lenses agree on (top quartile)."""
    ticker_hits: dict[str, list[str]] = {}
    for ticker, lenses in lens_scores.items():
        if not lenses:
            continue
        top = [l for l in lenses if l["score"] >= 65]
        if len(top) >= 2:
            ticker_hits[ticker] = [l["lens_id"] for l in top]

    disagreements: list[dict[str, Any]] = []
    for ticker, lenses in lens_scores.items():
        if len(lenses) < 2:
            continue
        high = lenses[0]["score"]
        low = lenses[-1]["score"]
        if high - low >= 25:
            disagreements.append(
                {
                    "ticker": ticker,
                    "best": lenses[0],
                    "worst": lenses[-1],
                    "spread": round(high - low, 1),
                }
            )

    return {
        "consensus": ticker_hits,
        "disagreements": sorted(disagreements, key=lambda d: d["spread"], reverse=True)[:8],
    }


def persist_scores(
    factor_rows: list[dict[str, Any]],
    lens_map: dict[str, list[dict[str, Any]]],
    as_of: str | None = None,
) -> None:
    as_of_date = as_of or date.today().isoformat()
    session = get_session()
    for row in factor_rows:
        session.add(
            FactorScoreRecord(
                as_of_date=as_of_date,
                ticker=row["ticker"],
                factors_json=json.dumps(row),
            )
        )
    for ticker, lenses in lens_map.items():
        for lens in lenses:
            session.add(
                StrategyLensScoreRecord(
                    as_of_date=as_of_date,
                    ticker=ticker,
                    lens_id=lens["lens_id"],
                    score=float(lens["score"]),
                    details_json=json.dumps(lens),
                )
            )
    session.commit()
    session.close()
