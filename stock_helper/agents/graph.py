from __future__ import annotations

import json
import operator
from datetime import date
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from stock_helper.agents.brief_diff import build_close_session_diff
from stock_helper.alerts.trends import build_weekly_trends_markdown
from stock_helper.agents.cost_tracker import get_active_tracker, reset_tracker
from stock_helper.agents.fallback import build_template_brief
from stock_helper.agents.persona import (
    brief_greeting,
    brief_system_prompt,
    get_persona,
    persona_disclaimer,
)
from stock_helper.agents.llm import LLMNotConfigured, invoke_json_node, invoke_node_llm
from stock_helper.collectors.fred import FREDClient
from stock_helper.collectors.ingest import load_recent_news
from stock_helper.collectors.market import (
    fetch_quotes,
    fetch_upcoming_earnings,
    fetch_upcoming_ipos,
    format_earnings_markdown,
    format_ipos_markdown,
    format_quotes_markdown,
    get_etf_tickers,
)
from stock_helper.config import has_llm_keys as config_has_llm
from stock_helper.storage.db import BriefRecord, get_session
from stock_helper.watchlist import get_core_tickers, list_agent_tracking


class BriefState(TypedDict):
    session: str
    news: list[dict]
    market: str
    earnings: str
    ipos: str
    macro: str
    sectors: str
    stocks: str
    agent_picks: str
    risk: str
    session_diff: str
    brief: str
    macro_score: float
    cost_notes: Annotated[list[str], operator.add]


SYSTEM = brief_system_prompt()

SESSION_PROFILES = {
    "morning": {
        "label": "Pre-Market Brief (before open)",
        "macro_task": (
            "Write a forward-looking macro backdrop for TODAY's US cash session. "
            "What headwinds/tailwinds should traders watch at the open?"
        ),
        "sector_task": (
            "Identify 3 sector themes to WATCH TODAY before/at the open. "
            "Format as markdown bullets: (+/-/neutral), catalyst, and why it matters today."
        ),
        "stock_task": (
            "Pre-market watchlist mode. For each ticker: (1) today's main catalyst or event, "
            "(2) why it belongs on today's focus list, (3) confidence 0-1, (4) horizon intraday/short. "
            "Mention relevant sector ETFs when helpful (e.g. QQQ, SMH, XLF, SPY). "
            "Max 80 words per ticker. Use ### TICKER headers."
        ),
        "risk_task": (
            "List what could invalidate today's watchlist: macro shocks, binary events, "
            "overconfidence, or missing data. Forward-looking bullets for today's session."
        ),
        "sections": {
            "market": "Pre-Market Snapshot",
            "earnings": "Watchlist Earnings — Today & This Week",
            "ipos": "Star IPO Radar",
            "macro": "Macro Backdrop for Today",
            "sectors": "Sectors to Watch",
            "stocks": "Today's Focus — Stocks & ETFs",
            "agent": "Also on Radar",
            "risk": "Today's Risk Flags",
        },
    },
    "close": {
        "label": "After-Hours Recap (post close)",
        "macro_task": (
            "Summarize how the macro environment shaped TODAY's session. "
            "Note any late-day or after-hours macro developments."
        ),
        "sector_task": (
            "Recap sector rotation TODAY: which sectors led/lagged and why. "
            "Format as markdown bullets with (+/-/neutral) and one-line attribution."
        ),
        "stock_task": (
            "End-of-day recap mode. For each ticker: (1) what happened today (news + price action), "
            "(2) attribution — why it moved, (3) confidence 0-1, (4) what to carry into tomorrow. "
            "Reference today's % change when inferable from context. Max 80 words per ticker. "
            "Use ### TICKER headers."
        ),
        "risk_task": (
            "Recap surprises vs expectations: contradictions, narrative shifts, or gaps in today's story. "
            "What risks remain for tomorrow?"
        ),
        "sections": {
            "diff": "Since Pre-Market Brief",
            "market": "Closing Snapshot",
            "earnings": "Up Next — Tonight & Tomorrow Pre-Market",
            "ipos": "Star IPO Radar",
            "macro": "Macro — Today's Take",
            "sectors": "Sector Recap",
            "stocks": "Stock Recap & Attribution",
            "agent": "Agent Tracking — Today",
            "risk": "Surprises & Remaining Risks",
        },
    },
    "weekly": {
        "label": "Weekly Wrap (Friday recap)",
        "macro_task": (
            "Summarize the WEEK's macro arc for US equities. How did the tone shift Mon→Fri? "
            "End with a forward-looking macro score for next week."
        ),
        "sector_task": (
            "Recap sector ROTATION this week: leaders, laggards, and narrative shifts. "
            "Format as markdown bullets with (+/-/neutral)."
        ),
        "stock_task": (
            "Weekly watchlist recap. For each core ticker: (1) week's key move/catalyst, "
            "(2) attribution, (3) what to carry into next week. Max 70 words each. "
            "Use ### TICKER headers."
        ),
        "risk_task": (
            "Week's surprises plus look-ahead for NEXT week: earnings clusters, macro data, "
            "positioning risks. Forward-looking bullets."
        ),
        "sections": {
            "trends": "This Week — Macro & Tracking",
            "market": "Weekly Performance Snapshot",
            "earnings": "Next Week — Earnings Watch",
            "ipos": "Star IPO Radar",
            "macro": "Macro — Week in Review",
            "sectors": "Sector Rotation This Week",
            "stocks": "Watchlist Weekly Recap",
            "agent": "Agent Tracking — This Week",
            "risk": "Look Ahead & Risks",
        },
    },
}


def _profile(session: str) -> dict:
    return SESSION_PROFILES.get(session, SESSION_PROFILES["morning"])


def collect_context(state: BriefState) -> dict:
    news = load_recent_news(limit=60)
    quotes = fetch_quotes(get_core_tickers())
    if state["session"] == "morning":
        quotes = quotes + fetch_quotes(get_etf_tickers())
    if state["session"] == "morning":
        quotes = quotes + fetch_quotes(get_etf_tickers())
    market = format_quotes_markdown(quotes)
    earn_days = 14 if state["session"] == "weekly" else 7
    earnings = format_earnings_markdown(
        fetch_upcoming_earnings(days=earn_days),
        session=state["session"],
    )
    ipos = format_ipos_markdown(fetch_upcoming_ipos(), session=state["session"])
    return {"news": news, "market": market, "earnings": earnings, "ipos": ipos}


def run_macro(state: BriefState) -> dict:
    tracker = get_active_tracker()
    profile = _profile(state["session"])
    fred = FREDClient()
    macro_data = fred.macro_snapshot()
    macro_text = "\n".join(
        f"- {m.get('label')}: {m.get('value')} ({m.get('date', 'n/a')})"
        for m in macro_data
    ) or "- FRED API key not set; infer macro tone from headlines only."
    headlines = "\n".join(f"- {n['headline']}" for n in state["news"][:15])
    user = (
        f"Session: {state['session']} — {profile['label']}\n\n"
        f"Macro data:\n{macro_text}\n\nHeadlines:\n{headlines}\n\n"
        f"{profile['macro_task']} "
        'Return JSON: {"macro_score": float, "paragraph": string}'
    )
    result = invoke_json_node("macro_agent", SYSTEM, user, tracker)
    paragraph = result.get("paragraph") or result.get("raw", "")
    score = float(result.get("macro_score", 0.0) or 0.0)
    return {
        "macro": paragraph,
        "macro_score": score,
        "cost_notes": [f"macro ~${tracker.session_spend:.4f} total"],
    }


def run_sector(state: BriefState) -> dict:
    tracker = get_active_tracker()
    profile = _profile(state["session"])
    headlines = "\n".join(
        f"- [{n.get('tickers')}] {n['headline']}" for n in state["news"][:25]
    )
    user = (
        f"Session: {state['session']} — {profile['label']}\n\n"
        f"{profile['sector_task']}\n\n{headlines}"
    )
    text = invoke_node_llm("sector_agent", SYSTEM, user, tracker)
    return {"sectors": text}


def run_stocks(state: BriefState) -> dict:
    tracker = get_active_tracker()
    core = get_core_tickers()
    by_ticker: dict[str, list[str]] = {t: [] for t in core}
    for n in state["news"]:
        for t in core:
            tickers = n.get("tickers") or ""
            if t in tickers or t in n.get("headline", ""):
                tag = n.get("event_type") or "news"
                by_ticker[t].append(f"[{tag}] {n['headline'][:100]}")
    blocks = []
    for t in core:
        lines = by_ticker[t][:3] or ["No major headlines in cache."]
        blocks.append(f"### {t}\n" + "\n".join(f"- {x}" for x in lines))
    user = (
        f"Session: {state['session']} — {_profile(state['session'])['label']}\n\n"
        f"{_profile(state['session'])['stock_task']}\n\n" + "\n\n".join(blocks)
    )
    text = invoke_node_llm("summarize_stock", SYSTEM, user, tracker)
    return {"stocks": text}


def run_agent_picks(state: BriefState) -> dict:
    rows = list_agent_tracking()
    if not rows:
        return {"agent_picks": "_No agent-tracked tickers._"}
    lines = []
    for r in rows[:10]:
        extra = load_recent_news(limit=5, ticker=r["ticker"])
        headline = extra[0]["headline"] if extra else "No recent headlines"
        lines.append(f"- **{r['ticker']}** ({r['reason']}): {headline[:80]}")
    return {"agent_picks": "\n".join(lines)}


def run_risk(state: BriefState) -> dict:
    tracker = get_active_tracker()
    profile = _profile(state["session"])
    user = (
        f"Session: {state['session']} — {profile['label']}\n\n"
        f"Macro score: {state.get('macro_score', 0)}\n\n"
        f"Macro:\n{state.get('macro', '')}\n\n"
        f"Sectors:\n{state.get('sectors', '')}\n\n"
        f"Stocks:\n{state.get('stocks', '')}\n\n"
        f"{profile['risk_task']}"
    )
    text = invoke_node_llm("risk_agent", SYSTEM, user, tracker)
    return {"risk": text}


def run_final_brief(state: BriefState) -> dict:
    today = date.today().isoformat()
    score = state.get("macro_score", 0.0)
    session = state["session"]

    session_diff = ""
    if session == "close":
        session_diff = build_close_session_diff(
            score,
            state.get("market", ""),
            state.get("stocks", ""),
        )
    elif session == "weekly":
        session_diff = build_weekly_trends_markdown()

    # Assemble in code so the email is never cut off by LLM max_tokens.
    text = assemble_brief_markdown(
        {**state, "session_diff": session_diff}, today, session, score
    )
    _save_brief(today, session, text, score)
    tracker = get_active_tracker()
    return {
        "brief": text,
        "cost_notes": [f"final assemble (no LLM) ~${tracker.session_spend:.4f} total"],
    }


def assemble_brief_markdown(
    state: BriefState, today: str, session: str, macro_score: float
) -> str:
    profile = _profile(session)
    titles = profile["sections"]
    session_titles = {
        "morning": "Pre-Market Brief",
        "close": "After-Hours Recap",
        "weekly": "Weekly Wrap",
    }
    session_title = session_titles.get(session, "Daily Brief")
    display = get_persona().get("display_name", "Moka-chan · Stock Helper")
    greeting = brief_greeting(session)

    sections = [
        f"# {display} — {session_title}",
        f"**Date:** {today} · **Session:** {profile['label']} · **Macro score:** {macro_score:+.2f}",
    ]
    if greeting:
        sections.extend(["", greeting, ""])

    if session == "close" and titles.get("diff"):
        sections.extend([
            f"## {titles['diff']}",
            state.get("session_diff", "").strip() or "_No diff available._",
            "",
        ])
    if session == "weekly" and titles.get("trends"):
        sections.extend([
            f"## {titles['trends']}",
            state.get("session_diff", "").strip() or "_No weekly trend data yet._",
            "",
        ])

    sections.extend([
        f"## {titles['market']}",
        state.get("market", "").strip() or "_No quote data._",
        "",
        f"## {titles['earnings']}",
        state.get("earnings", "").strip() or "_No upcoming earnings._",
        "",
        f"## {titles['ipos']}",
        state.get("ipos", "").strip() or "_No notable IPOs on radar._",
        "",
        f"## {titles['macro']}",
        state.get("macro", "").strip() or "_No macro analysis._",
        "",
        f"## {titles['sectors']}",
        state.get("sectors", "").strip() or "_No sector themes._",
        "",
        f"## {titles['stocks']}",
        state.get("stocks", "").strip() or "_No stock analysis._",
        "",
        f"## {titles['agent']}",
        state.get("agent_picks", "").strip() or "_None._",
        "",
        f"## {titles['risk']}",
        state.get("risk", "").strip() or "_No risk flags._",
        "",
        "---",
        "",
        persona_disclaimer(),
    ])
    return "\n".join(sections)


def _save_brief(brief_date: str, session: str, markdown: str, macro_score: float | None):
    snapshot = json.dumps(
        {"agent_tickers": [r["ticker"] for r in list_agent_tracking()]}
    )
    db = get_session()
    db.add(
        BriefRecord(
            brief_date=brief_date,
            session=session,
            markdown=markdown,
            macro_score=macro_score,
            snapshot_json=snapshot,
        )
    )
    db.commit()
    db.close()


def _empty_state(session: str) -> BriefState:
    return {
        "session": session,
        "news": [],
        "market": "",
        "earnings": "",
        "ipos": "",
        "macro": "",
        "sectors": "",
        "stocks": "",
        "agent_picks": "",
        "risk": "",
        "session_diff": "",
        "brief": "",
        "macro_score": 0.0,
        "cost_notes": [],
    }


def build_brief_graph():
    graph = StateGraph(BriefState)
    graph.add_node("collect", collect_context)
    graph.add_node("macro", run_macro)
    graph.add_node("sector", run_sector)
    graph.add_node("stocks", run_stocks)
    graph.add_node("agent_picks", run_agent_picks)
    graph.add_node("risk", run_risk)
    graph.add_node("final", run_final_brief)

    graph.add_edge(START, "collect")
    graph.add_edge("collect", "macro")
    graph.add_edge("macro", "sector")
    graph.add_edge("sector", "stocks")
    graph.add_edge("stocks", "agent_picks")
    graph.add_edge("agent_picks", "risk")
    graph.add_edge("risk", "final")
    graph.add_edge("final", END)
    return graph.compile()


def run_daily_brief(session: str = "morning") -> str:
    reset_tracker()
    state = _empty_state(session)

    # Always collect market/news context (works without LLM)
    collected = collect_context(state)
    state.update(collected)

    if not config_has_llm():
        text = build_template_brief(session)
        _save_brief(date.today().isoformat(), session, text, None)
        return text

    app = build_brief_graph()
    try:
        result = app.invoke(state)
        return result["brief"]
    except LLMNotConfigured:
        text = build_template_brief(session)
        _save_brief(date.today().isoformat(), session, text, None)
        return text
