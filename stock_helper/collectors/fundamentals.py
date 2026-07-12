from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from stock_helper.collectors.finnhub import FinnhubClient
from stock_helper.config import load_yaml
from stock_helper.storage.db import FundamentalSnapshot, get_session


def _analysis_cfg() -> dict[str, Any]:
    return load_yaml("analysis.yaml")


def fetch_ticker_metrics(ticker: str) -> dict[str, Any]:
    client = FinnhubClient()
    payload = client._get("/stock/metric", {"symbol": ticker.upper(), "metric": "all"}) or {}
    quote = client.quote(ticker.upper()) or {}
    metric = payload.get("metric") or {}
    return {
        "ticker": ticker.upper(),
        "quote": quote,
        "metric": metric,
        "series": payload.get("series") or {},
    }


def _max_age_days() -> int:
    return int((_analysis_cfg().get("data_refresh") or {}).get("fundamentals_max_age_days", 35))


def get_cached_fundamentals(ticker: str, max_age_days: int | None = None) -> dict[str, Any] | None:
    max_age = max_age_days if max_age_days is not None else _max_age_days()
    cutoff = (date.today() - timedelta(days=max_age)).isoformat()
    session = get_session()
    row = (
        session.query(FundamentalSnapshot)
        .filter(
            FundamentalSnapshot.ticker == ticker.upper(),
            FundamentalSnapshot.as_of_date >= cutoff,
        )
        .order_by(FundamentalSnapshot.id.desc())
        .first()
    )
    session.close()
    if not row:
        return None
    return json.loads(row.metrics_json)


def save_fundamentals(ticker: str, data: dict[str, Any], as_of: str | None = None) -> None:
    as_of_date = as_of or date.today().isoformat()
    session = get_session()
    session.add(
        FundamentalSnapshot(
            ticker=ticker.upper(),
            as_of_date=as_of_date,
            metrics_json=json.dumps(data, default=str),
        )
    )
    session.commit()
    session.close()


def refresh_fundamentals(tickers: list[str], force: bool = False) -> int:
    updated = 0
    for ticker in tickers:
        if not force:
            cached = get_cached_fundamentals(ticker)
            if cached:
                continue
        try:
            data = fetch_ticker_metrics(ticker)
            save_fundamentals(ticker, data)
            updated += 1
        except Exception:
            continue
    return updated


def load_fundamentals_map(tickers: list[str], refresh: bool = False) -> dict[str, dict[str, Any]]:
    if refresh:
        refresh_fundamentals(tickers, force=True)
    out: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        cached = get_cached_fundamentals(ticker)
        if cached:
            out[ticker.upper()] = cached
        else:
            try:
                data = fetch_ticker_metrics(ticker)
                save_fundamentals(ticker, data)
                out[ticker.upper()] = data
            except Exception:
                continue
    return out
