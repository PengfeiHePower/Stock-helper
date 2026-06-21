from __future__ import annotations

from datetime import date, datetime, timedelta

from stock_helper.storage.db import AgentTracking, BriefRecord, get_session
from stock_helper.watchlist import list_agent_tracking


def week_start(d: date | None = None) -> date:
    d = d or date.today()
    return d - timedelta(days=d.weekday())


def get_week_macro_scores() -> list[dict]:
    start = week_start().isoformat()
    session = get_session()
    rows = (
        session.query(BriefRecord)
        .filter(BriefRecord.brief_date >= start, BriefRecord.macro_score.isnot(None))
        .order_by(BriefRecord.brief_date, BriefRecord.id)
        .all()
    )
    session.close()

    out: list[dict] = []
    for row in rows:
        label = f"{row.brief_date} {row.session}"
        out.append({"label": label, "score": float(row.macro_score or 0.0)})
    return out


def get_week_agent_activity() -> dict:
    start_dt = datetime.combine(week_start(), datetime.min.time())
    session = get_session()
    added_rows = (
        session.query(AgentTracking)
        .filter(AgentTracking.added_at >= start_dt)
        .order_by(AgentTracking.added_at)
        .all()
    )
    session.close()

    current = list_agent_tracking()
    return {
        "added": [r.ticker for r in added_rows],
        "added_count": len(added_rows),
        "current_count": len(current),
        "current": [r["ticker"] for r in current],
    }


def build_weekly_trends_markdown() -> str:
    scores = get_week_macro_scores()
    agents = get_week_agent_activity()
    lines: list[str] = []

    if scores:
        first, last = scores[0], scores[-1]
        delta = last["score"] - first["score"]
        tone = "more optimistic" if delta > 0.05 else (
            "more cautious" if delta < -0.05 else "roughly unchanged"
        )
        lines.append(
            f"- **Macro score:** {first['score']:+.2f} ({first['label']}) → "
            f"{last['score']:+.2f} ({last['label']}) · _{tone}_"
        )
        if len(scores) > 2:
            path = " → ".join(f"{s['score']:+.2f}" for s in scores)
            lines.append(f"- **Path this week:** {path}")
    else:
        lines.append(
            "- **Macro score:** _No scored briefs yet this week — run morning/close briefs first._"
        )

    added = agents["added"]
    if added:
        lines.append(
            f"- **Agent tracking adds:** {agents['added_count']} "
            f"({', '.join(added)})"
        )
    else:
        lines.append("- **Agent tracking adds:** none this week")

    lines.append(f"- **Agent tracking now:** {agents['current_count']} tickers")
    if agents["current"]:
        lines.append(f"  - {', '.join(agents['current'][:12])}")

    return "\n".join(lines)
