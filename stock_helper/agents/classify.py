from __future__ import annotations

import json

from stock_helper.agents.cost_tracker import get_active_tracker
from stock_helper.agents.llm import has_llm_keys, invoke_json_node
from stock_helper.storage.db import NewsItem, get_session

CLASSIFY_SYSTEM = (
    "Classify US stock news. Return JSON only: "
    '{"event_type": "earnings|m_and_a|macro|product|legal|insider|other", '
    '"sentiment": "positive|negative|neutral", "tickers": ["AAPL"]}'
)


def classify_news_batch(limit: int = 20) -> int:
    """Classify unclassified news items using L1 model."""
    if not has_llm_keys(l1=True):
        return 0

    session = get_session()
    rows = (
        session.query(NewsItem)
        .filter(NewsItem.event_type.is_(None))
        .order_by(NewsItem.id.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        session.close()
        return 0

    tracker = get_active_tracker()
    updated = 0
    for row in rows:
        user = (
            f"Headline: {row.headline}\n"
            f"Summary: {(row.summary or '')[:400]}\n"
            f"Known tickers: {row.tickers or 'unknown'}"
        )
        try:
            result = invoke_json_node("classify_event", CLASSIFY_SYSTEM, user, tracker)
        except Exception:
            continue
        if result.get("event_type"):
            row.event_type = str(result["event_type"])[:64]
        if result.get("sentiment"):
            row.sentiment = str(result["sentiment"])[:32]
        if result.get("tickers") and not row.tickers:
            tickers = result["tickers"]
            if isinstance(tickers, list):
                row.tickers = ",".join(tickers)
        updated += 1

    session.commit()
    session.close()
    return updated
