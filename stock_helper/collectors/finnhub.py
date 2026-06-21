from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from stock_helper.config import get_settings


class FinnhubClient:
    BASE = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or get_settings().finnhub_api_key

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.api_key:
            return None
        params = dict(params or {})
        params["token"] = self.api_key
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(f"{self.BASE}{path}", params=params)
            resp.raise_for_status()
            return resp.json()

    def company_news(self, symbol: str, days_back: int = 3) -> list[dict]:
        from datetime import date, timedelta

        end = date.today()
        start = end - timedelta(days=days_back)
        data = self._get(
            "/company-news",
            {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()},
        )
        return data or []

    def market_news(self, category: str = "general") -> list[dict]:
        data = self._get("/news", {"category": category})
        return data or []

    def quote(self, symbol: str) -> dict | None:
        return self._get("/quote", {"symbol": symbol})

    def earnings_calendar(
        self, from_date: str, to_date: str, symbol: str | None = None
    ) -> dict:
        params: dict[str, Any] = {"from": from_date, "to": to_date}
        if symbol:
            params["symbol"] = symbol
        return self._get("/calendar/earnings", params) or {"earningsCalendar": []}

    def ipo_calendar(self, from_date: str, to_date: str) -> dict:
        return self._get(
            "/calendar/ipo", {"from": from_date, "to": to_date}
        ) or {"ipoCalendar": []}


def normalize_finnhub_news(raw: dict, symbol: str | None = None) -> dict:
    ts = raw.get("datetime")
    published = (
        datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
    )
    tickers = symbol or ",".join(raw.get("related", []) or [])
    ext_id = f"finnhub:{raw.get('id', raw.get('url', raw.get('headline')))}"
    return {
        "external_id": str(ext_id),
        "source": "finnhub",
        "headline": raw.get("headline", "")[:512],
        "summary": (raw.get("summary") or "")[:4000],
        "url": raw.get("url"),
        "tickers": tickers,
        "published_at": published,
    }
