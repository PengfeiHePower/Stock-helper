from __future__ import annotations

import json
from datetime import date
from typing import Any

from stock_helper.storage.db import StrategySnapshot, get_session


def save_strategy_snapshot(strategy: dict[str, Any]) -> None:
    session = get_session()
    regime = strategy.get("market_regime") or {}
    risk = strategy.get("risk_management") or {}
    session.add(
        StrategySnapshot(
            as_of_date=strategy.get("as_of_date") or date.today().isoformat(),
            snapshot_json=json.dumps(strategy, default=str),
            regime=regime.get("composite"),
            risk_level=strategy.get("risk_level"),
            risk_posture=risk.get("posture"),
            confidence=strategy.get("confidence"),
        )
    )
    session.commit()
    session.close()


def get_latest_strategy_snapshot() -> dict[str, Any] | None:
    session = get_session()
    row = session.query(StrategySnapshot).order_by(StrategySnapshot.id.desc()).first()
    session.close()
    if not row:
        return None
    data = json.loads(row.snapshot_json or "{}")
    data["_meta"] = {
        "as_of_date": row.as_of_date,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    return data


def get_prior_strategy_snapshot() -> dict[str, Any] | None:
    session = get_session()
    rows = (
        session.query(StrategySnapshot)
        .order_by(StrategySnapshot.id.desc())
        .limit(2)
        .all()
    )
    session.close()
    if len(rows) < 2:
        return None
    return json.loads(rows[1].snapshot_json or "{}")
