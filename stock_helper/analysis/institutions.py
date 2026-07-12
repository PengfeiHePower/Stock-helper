from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from stock_helper.collectors.sec_edgar import SECEdgarClient
from stock_helper.config import load_yaml


def load_institutions() -> list[dict[str, Any]]:
    cfg = load_yaml("institutions.yaml")
    if not cfg.get("enabled", True):
        return []
    return list(cfg.get("institutions") or [])


def institution_filing_status() -> list[dict[str, Any]]:
    """Track recent 13F-HR filings per institution (holdings parse = future work)."""
    client = SECEdgarClient()
    rows: list[dict[str, Any]] = []

    for inst in load_institutions():
        cik = inst.get("cik", "").lstrip("0")
        if not cik:
            continue
        try:
            data = client.submissions(cik.zfill(10))
        except Exception:
            rows.append({**inst, "status": "unavailable", "latest_13f": None})
            continue

        if not data:
            rows.append({**inst, "status": "not_found", "latest_13f": None})
            continue

        recent = data.get("filings", {}).get("recent", {})
        latest_13f = None
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        for form, filed in zip(forms, dates):
            if form in ("13F-HR", "13F-HR/A"):
                latest_13f = filed
                break

        rows.append(
            {
                **inst,
                "status": "ok" if latest_13f else "no_13f_found",
                "latest_13f": latest_13f,
                "strategy_lens": inst.get("strategy_lens"),
            }
        )
    return rows


def format_institutions_markdown(rows: list[dict[str, Any]]) -> str:
    lines = ["### Institution Strategy Tracking", ""]
    if not rows:
        lines.append("No institutions configured.")
        return "\n".join(lines)

    for row in rows:
        name = row.get("name", row.get("id"))
        lens = row.get("strategy_lens", "—")
        filed = row.get("latest_13f") or "—"
        lines.append(f"- **{name}** · lens `{lens}` · latest 13F: {filed}")

    lines.append("")
    lines.append(
        "13F holdings diff & theme extraction ship in a follow-up; "
        "filings are tracked via SEC EDGAR."
    )
    return "\n".join(lines)
