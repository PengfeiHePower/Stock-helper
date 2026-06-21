from __future__ import annotations

from functools import lru_cache
from typing import Any

from stock_helper.config import load_yaml


@lru_cache
def get_persona() -> dict[str, Any]:
    return load_yaml("persona.yaml")


def persona_name() -> str:
    return get_persona().get("name", "Saki")


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


def persona_disclaimer() -> str:
    return get_persona().get(
        "disclaimer",
        "*For informational purposes only. Not investment advice.*",
    )
