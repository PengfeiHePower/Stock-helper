from __future__ import annotations

import json
from datetime import date

from stock_helper.agents.cost_tracker import get_active_tracker
from stock_helper.agents.llm import invoke_node_llm
from stock_helper.agents.persona import brief_system_prompt
from stock_helper.collectors.ingest import load_news_since
from stock_helper.config import has_llm_keys
from stock_helper.storage.db import BriefRecord, get_session
from stock_helper.watchlist import list_agent_tracking

SYSTEM = brief_system_prompt()


def get_morning_brief(brief_date: str | None = None) -> BriefRecord | None:
    brief_date = brief_date or date.today().isoformat()
    session = get_session()
    row = (
        session.query(BriefRecord)
        .filter(BriefRecord.brief_date == brief_date, BriefRecord.session == "morning")
        .order_by(BriefRecord.id.desc())
        .first()
    )
    session.close()
    return row


def _agent_tickers_from_snapshot(record: BriefRecord | None) -> list[str]:
    if not record or not record.snapshot_json:
        return []
    try:
        data = json.loads(record.snapshot_json)
    except json.JSONDecodeError:
        return []
    return list(data.get("agent_tickers") or [])


def build_session_diff_facts(
    morning: BriefRecord | None, current_macro_score: float
) -> str:
    if not morning:
        return (
            "_No pre-market brief found for today — "
            "run `stock-helper brief --session morning` first._"
        )

    lines: list[str] = []
    morning_score = morning.macro_score
    if morning_score is not None:
        delta = current_macro_score - morning_score
        lines.append(
            f"- **Macro score:** {morning_score:+.2f} → "
            f"{current_macro_score:+.2f} ({delta:+.2f})"
        )
    else:
        lines.append(f"- **Macro score (close):** {current_macro_score:+.2f}")

    new_news = load_news_since(morning.created_at, limit=25)
    if new_news:
        lines.append(f"- **New headlines since pre-market ({len(new_news)}):**")
        for item in new_news[:8]:
            tickers = item.get("tickers") or "?"
            lines.append(f"  - [{tickers}] {item['headline'][:120]}")
        if len(new_news) > 8:
            lines.append(f"  - _…and {len(new_news) - 8} more_")
    else:
        lines.append("- **New headlines since pre-market:** none")

    morning_agents = set(_agent_tickers_from_snapshot(morning))
    current_agents = {r["ticker"] for r in list_agent_tracking()}
    added = sorted(current_agents - morning_agents)
    removed = sorted(morning_agents - current_agents)
    if added:
        lines.append(f"- **Agent tracking added:** {', '.join(added)}")
    if removed:
        lines.append(f"- **Agent tracking removed:** {', '.join(removed)}")
    if not added and not removed:
        lines.append("- **Agent tracking:** unchanged")

    return "\n".join(lines)


def build_session_diff_narrative(
    morning: BriefRecord,
    facts_md: str,
    market_md: str,
    stocks_md: str,
) -> str:
    if not has_llm_keys(l2=True):
        return ""

    tracker = get_active_tracker()
    user = (
        f"Pre-market brief (excerpt):\n{morning.markdown[:2800]}\n\n"
        f"Diff facts since pre-market:\n{facts_md}\n\n"
        f"Closing quotes:\n{market_md}\n\n"
        f"Stock recap draft:\n{stocks_md[:2000]}\n\n"
        "Write ### Morning vs Reality with 3-5 bullets. For each bullet: cite a specific "
        "pre-market theme or call, then say whether today's session confirmed, contradicted, "
        "or is still inconclusive. Be concrete — use tickers and moves. No disclaimer footer."
    )
    try:
        return invoke_node_llm("risk_agent", SYSTEM, user, tracker).strip()
    except Exception:
        return ""


def build_close_session_diff(
    current_macro_score: float,
    market_md: str,
    stocks_md: str,
) -> str:
    morning = get_morning_brief()
    facts = build_session_diff_facts(morning, current_macro_score)
    if not morning:
        return facts

    narrative = build_session_diff_narrative(
        morning, facts, market_md, stocks_md
    )
    if narrative:
        return f"{facts}\n\n{narrative}"
    return facts
