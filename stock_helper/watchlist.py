from __future__ import annotations

from datetime import datetime, timedelta

from stock_helper.config import load_yaml
from stock_helper.storage.db import AgentTracking, get_session


def get_core_tickers() -> list[str]:
    return list(load_yaml("watchlist.yaml").get("core", []))


def get_list_tickers(list_name: str | None = None) -> dict[str, list[str]] | list[str]:
    lists = load_yaml("watchlist.yaml").get("lists") or {}
    if list_name:
        return list(lists.get(list_name, []))
    return {k: list(v) for k, v in lists.items()}


def get_agent_tracking_tickers(active_only: bool = True) -> list[str]:
    session = get_session()
    q = session.query(AgentTracking)
    if active_only:
        now = datetime.utcnow()
        q = q.filter(
            (AgentTracking.expires_at.is_(None)) | (AgentTracking.expires_at > now)
        )
    tickers = [r.ticker for r in q.all()]
    session.close()
    return sorted(tickers)


def all_watchlist_tickers(include_agent: bool = True) -> list[str]:
    wl = load_yaml("watchlist.yaml")
    tickers: set[str] = set(wl.get("core", []))
    for symbols in (wl.get("lists") or {}).values():
        tickers.update(symbols)
    if include_agent:
        tickers.update(get_agent_tracking_tickers())
    return sorted(tickers)


def expire_agent_tracking() -> int:
    session = get_session()
    now = datetime.utcnow()
    rows = (
        session.query(AgentTracking)
        .filter(AgentTracking.expires_at.isnot(None), AgentTracking.expires_at <= now)
        .all()
    )
    for row in rows:
        session.delete(row)
    session.commit()
    count = len(rows)
    session.close()
    return count


def add_agent_tracking(ticker: str, reason: str) -> tuple[bool, str]:
    from stock_helper.validators import is_valid_ticker

    ticker = ticker.upper()
    if not is_valid_ticker(ticker):
        return False, f"{ticker} is not a valid ticker symbol."
    wl = load_yaml("watchlist.yaml")
    tracking_cfg = wl.get("agent_tracking") or {}
    max_size = tracking_cfg.get("max_size", 15)
    expire_days = tracking_cfg.get("auto_expire_days", 14)

    session = get_session()
    if session.query(AgentTracking).count() >= max_size:
        session.close()
        return False, f"Agent tracking list full (max {max_size})."

    existing = (
        session.query(AgentTracking).filter(AgentTracking.ticker == ticker).first()
    )
    if existing:
        session.close()
        return False, f"{ticker} already on agent tracking list."

    session.add(
        AgentTracking(
            ticker=ticker,
            reason=reason,
            expires_at=datetime.utcnow() + timedelta(days=expire_days),
        )
    )
    session.commit()
    session.close()
    return True, f"Added {ticker} to agent tracking for {expire_days} days."


def remove_agent_tracking(ticker: str) -> tuple[bool, str]:
    ticker = ticker.upper()
    session = get_session()
    row = session.query(AgentTracking).filter(AgentTracking.ticker == ticker).first()
    if not row:
        session.close()
        return False, f"{ticker} not on agent tracking list."
    session.delete(row)
    session.commit()
    session.close()
    return True, f"Removed {ticker} from agent tracking."


def list_agent_tracking() -> list[dict]:
    session = get_session()
    rows = session.query(AgentTracking).order_by(AgentTracking.added_at.desc()).all()
    out = [
        {
            "ticker": r.ticker,
            "reason": r.reason,
            "added_at": r.added_at.isoformat() if r.added_at else None,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        }
        for r in rows
    ]
    session.close()
    return out
