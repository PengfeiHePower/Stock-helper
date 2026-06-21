from __future__ import annotations

import re

from functools import lru_cache
from typing import Any

from stock_helper.config import load_yaml


@lru_cache
def get_persona() -> dict[str, Any]:
    return load_yaml("persona.yaml")


def persona_name() -> str:
    return get_persona().get("name", "Moka-chan")


def brief_system_prompt() -> str:
    p = get_persona()
    template = p.get("brief_system", "")
    return template.format(name=persona_name()).strip()


def chat_system_prompt() -> str:
    p = get_persona()
    template = p.get("chat_system", "")
    return template.format(name=persona_name()).strip()


def brief_greeting(session: str) -> str:
    greetings = get_persona().get("brief_greeting", {})
    return greetings.get(session, greetings.get("morning", ""))


def chat_greeting() -> str:
    template = get_persona().get("chat_greeting", "Hi~")
    return template.format(name=persona_name()).strip()


def chat_intro_reply(lang: str) -> str:
    """Short canned intro — no brief/news context."""
    intros = get_persona().get("chat_intro", {})
    if isinstance(intros, dict):
        template = intros.get(lang) or intros.get("zh") or intros.get("en", "Hi~ I'm {name}!")
    else:
        template = str(intros)
    return template.format(name=persona_name()).strip()


_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def detect_chat_language(message: str, thread_context: str = "") -> str:
    """Return 'zh' if the user is writing Chinese, else 'en'."""
    text = f"{message}\n{thread_context or ''}"
    if _CJK_RE.search(text):
        return "zh"
    return "en"


def chat_language_instruction(lang: str) -> str:
    if lang == "zh":
        return (
            "Reply language: 简体中文（必须）.\n"
            "你必须用中文回答本条消息；可把英文新闻/摘要译成中文。"
            "保留 ticker、数字、百分比原样。\n"
        )
    return "Reply language: English (required). Write your entire reply in English.\n"


def persona_disclaimer() -> str:
    return get_persona().get(
        "disclaimer",
        "*For informational purposes only. Not investment advice.*",
    )


_BOILERPLATE_MARKERS = (
    "remember, this is just",
    "always do your own research",
    "do your own research before",
    "not investment advice",
    "for informational purposes only",
    "the market is always moving",
)


def strip_chat_boilerplate(text: str) -> str:
    """Remove repetitive disclaimer sign-offs from chat replies."""
    blocks = text.rstrip().split("\n\n")
    while blocks:
        tail = blocks[-1].lower().strip()
        if len(tail) > 400 or not any(m in tail for m in _BOILERPLATE_MARKERS):
            break
        blocks.pop()

    result = "\n\n".join(blocks).rstrip()
    result = re.sub(
        r"(?<=[.!?])\s+(?:Remember,|Always do your own research).*?$",
        "",
        result,
        flags=re.IGNORECASE | re.DOTALL,
    ).rstrip()
    return result
