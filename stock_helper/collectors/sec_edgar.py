from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from stock_helper.config import get_settings


class SECEdgarClient:
    SUBMISSIONS = "https://data.sec.gov/submissions"
    SEARCH = "https://efts.sec.gov/LATEST/search-index"

    def __init__(self, user_agent: str | None = None):
        self.user_agent = user_agent or get_settings().sec_user_agent

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent, "Accept": "application/json"}

    def submissions(self, cik: str) -> dict | None:
        cik_padded = cik.zfill(10)
        url = f"{self.SUBMISSIONS}/CIK{cik_padded}.json"
        with httpx.Client(timeout=30.0, headers=self._headers()) as client:
            resp = client.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()

    def recent_filings_for_cik(
        self, cik: str, forms: set[str] | None = None, limit: int = 5
    ) -> list[dict]:
        data = self.submissions(cik)
        if not data:
            return []
        recent = data.get("filings", {}).get("recent", {})
        results: list[dict] = []
        forms = forms or {"8-K", "10-Q", "10-K", "4"}
        n = len(recent.get("form", []))
        for i in range(n):
            form = recent["form"][i]
            if form not in forms:
                continue
            filed = recent["filingDate"][i]
            accession = recent["accessionNumber"][i].replace("-", "")
            primary = recent["primaryDocument"][i]
            cik_num = str(data.get("cik", cik)).lstrip("0")
            url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik_num}/"
                f"{accession}/{primary}"
            )
            results.append(
                {
                    "external_id": f"sec:{accession}",
                    "source": "sec_edgar",
                    "headline": f"{data.get('name', cik)} filed {form} on {filed}",
                    "summary": f"Form {form} filing",
                    "url": url,
                    "tickers": ",".join(data.get("tickers") or []),
                    "published_at": datetime.strptime(filed, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    ),
                    "event_type": form.lower().replace("-", "_"),
                }
            )
            if len(results) >= limit:
                break
        return results


# Common CIKs for default watchlist (extend via DB later)
TICKER_CIK: dict[str, str] = {
    "AAPL": "320193",
    "MSFT": "789019",
    "NVDA": "1045810",
    "GOOGL": "1652044",
    "AMZN": "1018724",
    "META": "1326801",
    "TSLA": "1318605",
    "JPM": "19617",
    "V": "1403161",
    "UNH": "731766",
    "AMD": "2488",
    "AVGO": "1730168",
    "SMCI": "1375365",
    "JNJ": "200406",
    "PG": "80424",
    "KO": "21344",
}
