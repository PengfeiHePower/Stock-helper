from __future__ import annotations

import json
from datetime import date
from typing import Any

from stock_helper.storage.db import ReasoningSnapshot, get_session


def save_reasoning_snapshot(reasoning: dict[str, Any]) -> None:
    session = get_session()
    thesis = reasoning.get("thesis") or {}
    conflict = reasoning.get("conflict") or {}
    session.add(
        ReasoningSnapshot(
            as_of_date=reasoning.get("as_of_date") or date.today().isoformat(),
            snapshot_json=json.dumps(reasoning, default=str),
            thesis_headline=(thesis.get("headline") or "")[:512],
            overall_confidence=thesis.get("overall_confidence"),
            conflict_level=conflict.get("level"),
        )
    )
    session.commit()
    session.close()


def get_latest_reasoning_snapshot() -> dict[str, Any] | None:
    session = get_session()
    row = session.query(ReasoningSnapshot).order_by(ReasoningSnapshot.id.desc()).first()
    session.close()
    if not row:
        return None
    data = json.loads(row.snapshot_json or "{}")
    data["_meta"] = {
        "as_of_date": row.as_of_date,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    return data


def get_prior_reasoning_snapshot() -> dict[str, Any] | None:
    """Most recent saved snapshot (used as baseline before persisting the new run)."""
    session = get_session()
    row = session.query(ReasoningSnapshot).order_by(ReasoningSnapshot.id.desc()).first()
    session.close()
    if not row:
        return None
    return json.loads(row.snapshot_json or "{}")
