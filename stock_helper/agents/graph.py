from __future__ import annotations

import operator
from datetime import date
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from stock_helper.agents.cost_tracker import get_active_tracker, reset_tracker
from stock_helper.agents.fallback import build_template_brief
from stock_helper.agents.llm import LLMNotConfigured, invoke_json_node, invoke_node_llm
from stock_helper.collectors.fred import FREDClient
from stock_helper.collectors.ingest import load_recent_news
from stock_helper.collectors.market import (
    fetch_core_quotes,
    fetch_upcoming_earnings,
    format_earnings_markdown,
    format_quotes_markdown,
)
from stock_helper.config import has_llm_keys as config_has_llm
from stock_helper.storage.db import BriefRecord, get_session
from stock_helper.watchlist import get_core_tickers, list_agent_tracking


class BriefState(TypedDict):
    session: str
    news: list[dict]
    market: str
    earnings: str
    macro: str
    sectors: str
    stocks: str
    agent_picks: str
    risk: str
    brief: str
    macro_score: float
    cost_notes: Annotated[list[str], operator.add]


SYSTEM = (
    "You are a US equity research assistant. Be factual, cite uncertainty, "
    "and never give guaranteed buy/sell advice. Output concise markdown."
)


def collect_context(state: BriefState) -> dict:
    news = load_recent_news(limit=60)
    quotes = format_quotes_markdown(fetch_core_quotes())
    earnings = format_earnings_markdown(fetch_upcoming_earnings())
    return {"news": news, "market": quotes, "earnings": earnings}


def run_macro(state: BriefState) -> dict:
    tracker = get_active_tracker()
    fred = FREDClient()
    macro_data = fred.macro_snapshot()
    macro_text = "\n".join(
        f"- {m.get('label')}: {m.get('value')} ({m.get('date', 'n/a')})"
        for m in macro_data
    ) or "- FRED API key not set; infer macro tone from headlines only."
    headlines = "\n".join(f"- {n['headline']}" for n in state["news"][:15])
    user = (
        f"Macro data:\n{macro_text}\n\nHeadlines:\n{headlines}\n\n"
        "Write a macro environment paragraph and score from -1 (bearish) to +1 (bullish). "
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
    headlines = "\n".join(
        f"- [{n.get('tickers')}] {n['headline']}" for n in state["news"][:25]
    )
    user = (
        "From these headlines, identify 3 sector themes for US equities today. "
        "Format as markdown bullets with (+/-/neutral) and one-line catalyst.\n\n"
        f"{headlines}"
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
        "Expand each ticker: event, impact, confidence 0-1, horizon short/mid. "
        "Max 80 words per ticker. Use ### TICKER headers. Finish every ticker block completely.\n\n"
        + "\n\n".join(blocks)
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
    user = (
        f"Macro score: {state.get('macro_score', 0)}\n\n"
        f"Macro:\n{state.get('macro', '')}\n\n"
        f"Sectors:\n{state.get('sectors', '')}\n\n"
        f"Stocks:\n{state.get('stocks', '')}\n\n"
        "List conflicts, overconfidence, or missing data as markdown bullets."
    )
    text = invoke_node_llm("risk_agent", SYSTEM, user, tracker)
    return {"risk": text}


def run_final_brief(state: BriefState) -> dict:
    today = date.today().isoformat()
    score = state.get("macro_score", 0.0)
    session = state["session"]

    # Assemble in code so the email is never cut off by LLM max_tokens.
    text = assemble_brief_markdown(state, today, session, score)
    _save_brief(today, session, text, score)
    tracker = get_active_tracker()
    return {
        "brief": text,
        "cost_notes": [f"final assemble (no LLM) ~${tracker.session_spend:.4f} total"],
    }


def assemble_brief_markdown(
    state: BriefState, today: str, session: str, macro_score: float
) -> str:
    sections = [
        "# Stock Helper Daily Brief",
        f"**Date:** {today} · **Session:** {session} · **Macro score:** {macro_score:+.2f}",
        "",
        "## Market Snapshot",
        state.get("market", "").strip() or "_No quote data._",
        "",
        "## Earnings This Week",
        state.get("earnings", "").strip() or "_No upcoming earnings._",
        "",
        "## Macro Environment",
        state.get("macro", "").strip() or "_No macro analysis._",
        "",
        "## Sector Themes",
        state.get("sectors", "").strip() or "_No sector themes._",
        "",
        "## Core Watchlist",
        state.get("stocks", "").strip() or "_No stock analysis._",
        "",
        "## Agent Tracking",
        state.get("agent_picks", "").strip() or "_None._",
        "",
        "## Risk & Conflicts",
        state.get("risk", "").strip() or "_No risk flags._",
        "",
        "---",
        "",
        "*For informational purposes only. Not investment advice.*",
    ]
    return "\n".join(sections)


def _save_brief(brief_date: str, session: str, markdown: str, macro_score: float | None):
    db = get_session()
    db.add(
        BriefRecord(
            brief_date=brief_date,
            session=session,
            markdown=markdown,
            macro_score=macro_score,
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
        "macro": "",
        "sectors": "",
        "stocks": "",
        "agent_picks": "",
        "risk": "",
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
