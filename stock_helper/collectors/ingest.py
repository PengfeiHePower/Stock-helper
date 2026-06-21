from __future__ import annotations

import logging
import time
from datetime import datetime

from stock_helper.collectors.finnhub import FinnhubClient, normalize_finnhub_news
from stock_helper.collectors.sec_edgar import SECEdgarClient, TICKER_CIK
from stock_helper.config import get_settings
from stock_helper.storage.db import NewsItem, get_session
from stock_helper.watchlist import all_watchlist_tickers

logger = logging.getLogger(__name__)


def ingest_watchlist_news(days_back: int = 2) -> int:
    """Fetch Finnhub + SEC filings for watchlist tickers; return new item count."""
    settings = get_settings()
    if not settings.finnhub_api_key:
        logger.warning("FINNHUB_API_KEY not set — skipping Finnhub ingest")

    finnhub = FinnhubClient()
    sec = SECEdgarClient()
    session = get_session()
    added = 0
    errors: list[str] = []

    tickers = all_watchlist_tickers(include_agent=True)
    for symbol in tickers:
        try:
            for raw in finnhub.company_news(symbol, days_back=days_back):
                item = normalize_finnhub_news(raw, symbol=symbol)
                if _save_news(session, item):
                    added += 1
        except Exception as e:
            errors.append(f"{symbol} finnhub: {e}")

        cik = TICKER_CIK.get(symbol)
        if cik:
            try:
                time.sleep(0.12)  # SEC fair access ~10 req/s
                for filing in sec.recent_filings_for_cik(cik, limit=2):
                    if _save_news(session, filing):
                        added += 1
            except Exception as e:
                errors.append(f"{symbol} sec: {e}")

    market_added = 0
    try:
        for raw in finnhub.market_news():
            item = normalize_finnhub_news(raw)
            if _save_news(session, item):
                added += 1
                market_added += 1
            if market_added >= 30:
                break
    except Exception as e:
        errors.append(f"market news: {e}")

    session.commit()
    session.close()

    for err in errors[:5]:
        logger.warning("Ingest error: %s", err)
    if len(errors) > 5:
        logger.warning("... and %d more ingest errors", len(errors) - 5)

    return added


def _save_news(session, item: dict) -> bool:
    exists = (
        session.query(NewsItem)
        .filter(NewsItem.external_id == item["external_id"])
        .first()
    )
    if exists:
        return False
    session.add(
        NewsItem(
            external_id=item["external_id"],
            source=item["source"],
            headline=item["headline"],
            summary=item.get("summary"),
            url=item.get("url"),
            tickers=item.get("tickers", ""),
            published_at=item.get("published_at"),
            event_type=item.get("event_type"),
        )
    )
    return True


def load_recent_news(limit: int = 80, ticker: str | None = None) -> list[dict]:
    session = get_session()
    q = session.query(NewsItem)
    if ticker:
        pattern = f"%{ticker.upper()}%"
        q = q.filter(
            (NewsItem.tickers.like(pattern)) | (NewsItem.headline.like(pattern))
        )
    rows = (
        q.order_by(NewsItem.published_at.desc().nullslast(), NewsItem.id.desc())
        .limit(limit)
        .all()
    )
    out = [
        {
            "headline": r.headline,
            "summary": r.summary or "",
            "source": r.source,
            "tickers": r.tickers,
            "url": r.url,
            "event_type": r.event_type,
            "sentiment": r.sentiment,
        }
        for r in rows
    ]
    session.close()
    return out


def load_news_since(since: datetime, limit: int = 30) -> list[dict]:
    session = get_session()
    rows = (
        session.query(NewsItem)
        .filter(NewsItem.created_at > since)
        .order_by(NewsItem.published_at.desc().nullslast(), NewsItem.id.desc())
        .limit(limit)
        .all()
    )
    out = [
        {
            "external_id": r.external_id,
            "headline": r.headline,
            "summary": r.summary or "",
            "source": r.source,
            "tickers": r.tickers,
            "url": r.url,
            "event_type": r.event_type,
            "sentiment": r.sentiment,
        }
        for r in rows
    ]
    session.close()
    return out


def news_count() -> int:
    session = get_session()
    count = session.query(NewsItem).count()
    session.close()
    return count
