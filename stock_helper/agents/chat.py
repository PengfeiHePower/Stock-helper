from __future__ import annotations

from stock_helper.agents.cost_tracker import BudgetExceeded, reset_tracker
from stock_helper.agents.llm import LLMNotConfigured, invoke_node_llm
from stock_helper.collectors.ingest import load_recent_news
from stock_helper.storage.db import BriefRecord, get_session
from stock_helper.watchlist import (
    all_watchlist_tickers,
    get_core_tickers,
    list_agent_tracking,
)

from stock_helper.agents.persona import (
    chat_intro_reply,
    chat_language_instruction,
    chat_system_prompt,
    detect_chat_language,
    strip_chat_boilerplate,
)
from stock_helper.agents.watchlist_chat import handle_natural_watchlist

SYSTEM = chat_system_prompt()

_INTRO_GREETINGS = frozenset(
    {"hi", "hello", "hey", "你好", "哈喽", "嗨", "在吗", "你是谁", "who are you"}
)
_INTRO_PHRASES = (
    "介绍自己",
    "介绍一下自己",
    "介绍一下你",
    "介绍下自己",
    "介绍下你",
    "你是什么",
    "你能做什么",
    "你会什么",
    "你能干嘛",
    "你是干嘛",
    "introduce yourself",
    "what can you do",
    "what are you",
)
_MARKET_HINTS = (
    "市场",
    "宏观",
    "行业",
    "股票",
    "新闻",
    "brief",
    "watchlist",
    "涨",
    "跌",
    "财报",
    "怎么样",
    "如何",
    "today",
    "outlook",
    "analysis",
)


def is_meta_intro_message(message: str) -> bool:
    """True when user wants bot identity/capabilities, not market analysis."""
    lower = message.lower().strip()
    compact = lower.replace(" ", "")

    if any(h in lower for h in _MARKET_HINTS):
        return False
    if any(t in message.upper() for t in get_core_tickers()):
        return False

    if lower in _INTRO_GREETINGS or compact in _INTRO_GREETINGS:
        return True
    if any(p in lower or p in compact for p in _INTRO_PHRASES):
        return True
    if "介绍" in lower and len(message) <= 24:
        return True
    return False


def route_chat_intent(message: str) -> str:
    lower = message.lower()
    if any(
        k in lower
        for k in (
            "deep",
            "detailed",
            "compare",
            "portfolio",
            "risk",
            "详细",
            "对比",
            "持仓",
            "风险",
        )
    ):
        return "chat_deep"
    if any(
        k in lower
        for k in (
            "why",
            "analysis",
            "impact",
            "outlook",
            "为什么",
            "分析",
            "影响",
            "展望",
            "市场",
            "宏观",
            "行业",
            "概览",
            "怎么样",
            "如何",
            "今天",
            "聊聊",
        )
    ):
        return "chat_analytical"
    return "chat_simple"


def chat_reply(message: str, thread_context: str = "") -> str:
    lower = message.lower().strip()
    lang = detect_chat_language(message, thread_context)

    if lower in ("watchlist", "list watchlist", "show watchlist"):
        return format_watchlist_summary()

    if is_meta_intro_message(message):
        return chat_intro_reply(lang)

    wl_reply = handle_natural_watchlist(message, lang)
    if wl_reply:
        return wl_reply

    tracker = reset_tracker()
    try:
        tracker.check_chat_budget()
    except BudgetExceeded as e:
        return str(e)

    node = route_chat_intent(message)
    session = get_session()
    latest = session.query(BriefRecord).order_by(BriefRecord.id.desc()).first()
    session.close()

    brief_excerpt = latest.markdown[:3000] if latest else "No brief yet."
    news = load_recent_news(limit=15)
    news_text = "\n".join(
        f"- [{n.get('tickers')}] {n['headline']}" for n in news
    )
    agent_text = format_agent_tracking_lines()

    user = (
        f"{chat_language_instruction(lang)}\n"
        f"User message: {message}\n\n"
        f"Thread context:\n{thread_context or 'none'}\n\n"
        f"Core watchlist: {', '.join(get_core_tickers())}\n\n"
        f"Agent tracking:\n{agent_text}\n\n"
        f"Latest brief excerpt:\n{brief_excerpt}\n\n"
        f"Recent headlines:\n{news_text}"
    )
    try:
        reply = invoke_node_llm(node, SYSTEM, user, tracker)
        return strip_chat_boilerplate(reply)
    except (BudgetExceeded, LLMNotConfigured) as e:
        return str(e) if str(e) else (
            "LLM not configured. Set GOOGLE_API_KEY and ANTHROPIC_API_KEY in .env"
        )


def format_watchlist_summary() -> str:
    core = get_core_tickers()
    agent = list_agent_tracking()
    lines = [
        f"*Core ({len(core)}):* {', '.join(core)}",
        f"*All tracked ({len(all_watchlist_tickers())}):* {', '.join(all_watchlist_tickers())}",
    ]
    if agent:
        lines.append("*Agent tracking:*")
        for r in agent:
            lines.append(f"  • {r['ticker']} — {r['reason']}")
    lines.append("\nChat: 关注 AMD | 不再关注 AMD | follow NVDA | unfollow TSLA")
    lines.append("Commands: `track TICKER` | `untrack TICKER`")
    return "\n".join(lines)


def format_agent_tracking_lines() -> str:
    rows = list_agent_tracking()
    if not rows:
        return "- none"
    return "\n".join(f"- {r['ticker']}: {r['reason']}" for r in rows)


def handle_watchlist_command(message: str) -> str | None:
    parts = message.strip().split()
    if len(parts) != 2:
        return None
    cmd, ticker = parts[0].lower(), parts[1].upper()
    lang = "en"
    if cmd == "track":
        from stock_helper.agents.watchlist_chat import _format_add_result
        from stock_helper.watchlist import add_agent_tracking

        ok, detail = add_agent_tracking(ticker, "Added via chat")
        return _format_add_result(lang, ticker, ok, detail)
    if cmd == "untrack":
        from stock_helper.agents.watchlist_chat import _format_remove_result
        from stock_helper.watchlist import remove_agent_tracking

        ok, detail = remove_agent_tracking(ticker)
        return _format_remove_result(lang, ticker, ok, detail)
    return None
