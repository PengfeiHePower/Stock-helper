from __future__ import annotations

import time
from typing import Any

import httpx

from stock_helper.config import get_settings


class FREDClient:
    BASE = "https://api.stlouisfed.org/fred"

    SERIES = {
        "fed_funds": "DFF",
        "cpi": "CPIAUCSL",
        "unemployment": "UNRATE",
        "vix": "VIXCLS",
        "ten_year_yield": "DGS10",
    }

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else get_settings().fred_api_key

    def latest_observation(self, series_id: str) -> dict[str, Any] | None:
        if not self.api_key:
            return None
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(f"{self.BASE}/series/observations", params=params)
            resp.raise_for_status()
            obs = resp.json().get("observations", [])
            if not obs:
                return None
            return {"series_id": series_id, **obs[0]}

    def macro_snapshot(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for label, sid in self.SERIES.items():
            obs = self.latest_observation(sid)
            if obs:
                out.append({"label": label, **obs})
        return out
