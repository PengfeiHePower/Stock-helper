from __future__ import annotations

from typing import Any

import httpx

from stock_helper.config import get_settings, load_yaml


class MacroSeriesClient:
    """FRED time-series for rule-based macro classification."""

    BASE = "https://api.stlouisfed.org/fred"

    DEFAULT_SERIES = {
        "fed_funds": "DFF",
        "cpi": "CPIAUCSL",
        "unemployment": "UNRATE",
        "vix": "VIXCLS",
        "ten_year_yield": "DGS10",
        "two_year_yield": "DGS2",
        "yield_curve_spread": "T10Y2Y",
    }

    def __init__(self, api_key: str | None = None, series_ids: dict[str, str] | None = None):
        self.api_key = api_key if api_key is not None else get_settings().fred_api_key
        if series_ids:
            self.series_ids = series_ids
        else:
            cfg = load_yaml("macro_series.yaml")
            self.series_ids = cfg.get("series") or self.DEFAULT_SERIES

    def observations(
        self, series_id: str, limit: int = 12, sort_order: str = "desc"
    ) -> list[dict[str, Any]]:
        if not self.api_key:
            return []
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": sort_order,
            "limit": limit,
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(f"{self.BASE}/series/observations", params=params)
            resp.raise_for_status()
            return resp.json().get("observations", [])

    def fetch_series(self, label: str, series_id: str, limit: int = 14) -> list[dict]:
        try:
            history = self.observations(series_id, limit=limit, sort_order="desc")
        except Exception:
            return []
        values: list[dict] = []
        for row in reversed(history):
            v = row.get("value")
            if v in (".", None):
                continue
            try:
                values.append({"date": row["date"], "value": float(v)})
            except ValueError:
                continue
        return values

    def fetch_all(self, limit: int = 14) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for label, sid in self.series_ids.items():
            out[label] = self.fetch_series(label, sid, limit=limit)
        return out

    def latest_value(self, series_id: str) -> float | None:
        obs = self.observations(series_id, limit=1)
        if not obs or obs[0].get("value") in (".", None):
            return None
        try:
            return float(obs[0]["value"])
        except ValueError:
            return None

    def macro_dashboard(self) -> dict[str, Any]:
        """Legacy compact dashboard (backward compatible)."""
        out: dict[str, Any] = {"series": {}, "latest": {}}
        for label, sid in self.series_ids.items():
            if label not in (
                "fed_funds",
                "cpi",
                "unemployment",
                "vix",
                "ten_year_yield",
                "yield_curve_spread",
            ):
                continue
            history = self.fetch_series(label, sid, limit=6)
            out["series"][label] = history
            if history:
                out["latest"][label] = history[-1]["value"]
        return out
