"""Remove invalid agent-tracking entries (e.g. FORM, INC from bad regex runs)."""

from __future__ import annotations

from stock_helper.validators import is_valid_ticker
from stock_helper.storage.db import AgentTracking, get_session


def purge_invalid_agent_tracking() -> int:
    session = get_session()
    rows = session.query(AgentTracking).all()
    removed = 0
    for row in rows:
        if not is_valid_ticker(row.ticker):
            session.delete(row)
            removed += 1
    session.commit()
    session.close()
    return removed


if __name__ == "__main__":
    print(f"Removed {purge_invalid_agent_tracking()} invalid entries")
