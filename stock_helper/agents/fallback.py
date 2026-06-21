from __future__ import annotations

from datetime import date

from stock_helper.collectors.ingest import load_recent_news
from stock_helper.collectors.market import (
    fetch_core_quotes,
    fetch_upcoming_earnings,
    format_earnings_markdown,
    format_quotes_markdown,
)
from stock_helper.agents.persona import brief_greeting, get_persona, persona_disclaimer, persona_name
from stock_helper.watchlist import get_core_tickers, list_agent_tracking


def build_template_brief(session: str) -> str:
    """Non-LLM brief when API keys are missing — still useful for testing pipeline."""
    today = date.today().isoformat()
    quotes = format_quotes_markdown(fetch_core_quotes())
    earnings = format_earnings_markdown(fetch_upcoming_earnings())
    news = load_recent_news(limit=20)
    headlines = "\n".join(
        f"- [{n.get('tickers') or '?'}] {n['headline']}" for n in news[:15]
    ) or "- No news in database. Run `stock-helper ingest` first."

    agent_rows = list_agent_tracking()
    agent_section = (
        "\n".join(f"- **{r['ticker']}**: {r['reason']}" for r in agent_rows[:10])
        or "- None"
    )

    display = get_persona().get("display_name", "Moka-chan · Stock Helper")
    greeting = brief_greeting(session)

    return f"""# {display} — template mode (no LLM keys yet~)
**Date:** {today} | **Session:** {session}

{greeting}

## Market Snapshot
{quotes}

## Earnings This Week (Core)
{earnings}

## Top Headlines
{headlines}

## Agent Tracking
{agent_section}

## Risk
- Template mode~ Set GOOGLE_API_KEY and ANTHROPIC_API_KEY for the full {persona_name()} experience ✨

---
{persona_disclaimer()}
"""
