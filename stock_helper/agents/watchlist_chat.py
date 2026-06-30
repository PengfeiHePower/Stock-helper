from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from stock_helper.validators import is_valid_ticker
from stock_helper.watchlist import (
    add_agent_tracking,
    all_watchlist_tickers,
    get_core_tickers,
    remove_agent_tracking,
)

WatchlistAction = Literal["add", "remove", "show"]

_SHOW_PHRASES = (
    "关注列表",
    "跟踪列表",
    "我的关注",
    "我的跟踪",
    "关注什么",
    "在关注什么",
    "show watchlist",
    "show my watchlist",
    "list watchlist",
    "my watchlist",
    "what am i watching",
    "what am i following",
)

_REMOVE_PHRASES = (
    "不再关注",
    "取消关注",
    "不关注了",
    "不想关注",
    "不要关注",
    "不再跟踪",
    "取消跟踪",
    "不想跟踪",
    "不要跟踪",
    "移除",
    "删掉",
    "去掉",
    "删除",
    "unfollow",
    "untrack",
    "stop following",
    "stop tracking",
    "no longer follow",
    "no longer track",
    "don't follow",
    "dont follow",
    "remove from watchlist",
    "remove from my watchlist",
)

_ADD_PHRASES = (
    "想关注",
    "要关注",
    "帮我关注",
    "帮忙关注",
    "加入关注",
    "加入跟踪",
    "加入watchlist",
    "加入 watchlist",
    "添加到",
    "添加",
    "加上",
    "跟踪",
    "关注",
    "follow",
    "add to watchlist",
    "add to my watchlist",
    "start following",
    "start tracking",
    "track",
    "watch ",
)

_TICKER_RE = re.compile(r"(?<![A-Z])([A-Z]{2,5})(?![A-Z])")


@dataclass(frozen=True)
class WatchlistIntent:
    action: WatchlistAction
    tickers: tuple[str, ...]


def extract_tickers(message: str) -> list[str]:
    upper = message.upper()
    seen: set[str] = set()
    out: list[str] = []
    for match in _TICKER_RE.finditer(upper):
        ticker = match.group(1)
        if ticker in seen or not is_valid_ticker(ticker):
            continue
        seen.add(ticker)
        out.append(ticker)
    return out


def _contains_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    lower = text.lower()
    compact = lower.replace(" ", "")
    return any(p in lower or p.replace(" ", "") in compact for p in phrases)


def parse_watchlist_intent(message: str) -> WatchlistIntent | None:
    text = message.strip()
    if not text:
        return None

    lower = text.lower()
    compact = lower.replace(" ", "")

    if lower in ("watchlist", "list watchlist", "show watchlist"):
        return WatchlistIntent("show", ())

    if _contains_phrase(text, _SHOW_PHRASES):
        tickers = extract_tickers(text)
        if tickers:
            return None
        return WatchlistIntent("show", ())

    if _contains_phrase(text, _REMOVE_PHRASES):
        tickers = extract_tickers(text)
        if tickers:
            return WatchlistIntent("remove", tuple(tickers))
        return None

    if _contains_phrase(text, _ADD_PHRASES):
        if any(w in lower for w in ("为什么", "怎么", "如何", "why", "how")):
            return None
        tickers = extract_tickers(text)
        if tickers:
            return WatchlistIntent("add", tuple(tickers))
        if any(
            p in lower or p.replace(" ", "") in compact
            for p in (
                "想关注",
                "要关注",
                "帮我关注",
                "帮忙关注",
                "follow",
                "add to watchlist",
                "add to my watchlist",
            )
        ):
            return WatchlistIntent("add", ())
        return None

    if re.search(r"\b(track|untrack)\b", lower):
        tickers = extract_tickers(text)
        if not tickers:
            return None
        action: WatchlistAction = "remove" if "untrack" in lower else "add"
        return WatchlistIntent(action, tuple(tickers))

    return None


def _reply(lang: str, zh: str, en: str) -> str:
    return zh if lang == "zh" else en


def _format_add_result(lang: str, ticker: str, ok: bool, detail: str) -> str:
    tracked = set(all_watchlist_tickers())
    if ok:
        return _reply(
            lang,
            f"好哒~ 已经把 {ticker} 加进追踪列表啦！接下来 brief 和 alert 都会带上它 ✨",
            f"Done~ {ticker} is on your tracking list now. Briefs and alerts will include it ✨",
        )
    if f"{ticker} already" in detail.lower() or ticker in tracked:
        return _reply(
            lang,
            f"{ticker} 已经在 watchlist 里啦，不用再加了~",
            f"{ticker} is already on your watchlist~",
        )
    if "full" in detail.lower():
        return _reply(
            lang,
            f"追踪列表已满，暂时加不了 {ticker} 了… 先用 /untrack 腾个位置吧。",
            f"Tracking list is full — can't add {ticker}. Use /untrack to free a slot.",
        )
    return _reply(
        lang,
        f"没能加上 {ticker}：{detail}",
        f"Couldn't add {ticker}: {detail}",
    )


def _format_remove_result(lang: str, ticker: str, ok: bool, detail: str) -> str:
    if ok:
        return _reply(
            lang,
            f"收到~ 已经把 {ticker} 从 agent tracking 移除啦。",
            f"Got it~ Removed {ticker} from agent tracking.",
        )
    core = set(get_core_tickers())
    if ticker in core:
        return _reply(
            lang,
            f"{ticker} 在核心 watchlist 里，会一直出现在 brief 中；"
            f"它不在可移除的 agent tracking 列表里哦。",
            f"{ticker} is on the core watchlist and stays in every brief; "
            f"it's not on the removable agent-tracking list.",
        )
    return _reply(
        lang,
        f"{ticker} 不在 agent tracking 里，所以没删成~",
        f"{ticker} wasn't on agent tracking, so nothing to remove~",
    )


def handle_natural_watchlist(message: str, lang: str = "en") -> str | None:
    intent = parse_watchlist_intent(message)
    if not intent:
        return None

    if intent.action == "show":
        from stock_helper.agents.chat import format_watchlist_summary

        return format_watchlist_summary().replace("*", "")

    if intent.action == "add":
        if not intent.tickers:
            return _reply(
                lang,
                "想关注哪只股票呀？直接说 ticker 就行，比如：「关注 AMD」",
                "Which ticker should I add? Say something like: follow AMD",
            )
        lines = [
            _format_add_result(
                lang,
                ticker,
                *add_agent_tracking(ticker, "Added via chat"),
            )
            for ticker in intent.tickers
        ]
        return "\n".join(lines)

    lines = []
    for ticker in intent.tickers:
        ok, detail = remove_agent_tracking(ticker)
        lines.append(_format_remove_result(lang, ticker, ok, detail))
    return "\n".join(lines)
