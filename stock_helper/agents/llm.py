from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

from stock_helper.agents.cost_tracker import CostTracker, get_active_tracker, get_model_for_node
from stock_helper.config import get_settings, has_llm_keys as _has_llm_keys


def has_llm_keys(l1: bool = False, l2: bool = False) -> bool:
    return _has_llm_keys(l1=l1, l2=l2)


class LLMNotConfigured(Exception):
    pass


def _ensure_env(model_id: str) -> None:
    s = get_settings()
    if model_id.startswith("gemini/"):
        if not os.getenv("GOOGLE_API_KEY") and s.google_api_key:
            os.environ["GOOGLE_API_KEY"] = s.google_api_key
        if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
    if model_id.startswith("anthropic/") and s.anthropic_api_key:
        if not os.getenv("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = s.anthropic_api_key


def _require_keys_for_node(node: str) -> None:
    cfg = get_model_for_node(node)
    tier = cfg["tier"]
    if tier == "l1" and not has_llm_keys(l1=True):
        raise LLMNotConfigured("GOOGLE_API_KEY required for L1 nodes")
    if tier in ("l2", "l3") and not has_llm_keys(l2=True):
        raise LLMNotConfigured("ANTHROPIC_API_KEY required for L2/L3 nodes")


def build_chat_model(node: str) -> tuple[BaseChatModel, str, str]:
    _require_keys_for_node(node)
    cfg = get_model_for_node(node)
    model_id = cfg["model"]
    _ensure_env(model_id)

    if model_id.startswith("gemini/"):
        from langchain_google_genai import ChatGoogleGenerativeAI

        name = model_id.split("/", 1)[1]
        llm = ChatGoogleGenerativeAI(
            model=name,
            temperature=cfg.get("temperature", 0),
            max_output_tokens=cfg.get("max_tokens", 512),
        )
    elif model_id.startswith("anthropic/"):
        from langchain_anthropic import ChatAnthropic

        name = model_id.split("/", 1)[1]
        llm = ChatAnthropic(
            model=name,
            temperature=cfg.get("temperature", 0.2),
            max_tokens=cfg.get("max_tokens", 2048),
        )
    else:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model=model_id, temperature=cfg.get("temperature", 0))

    return llm, model_id, cfg["tier"]


_CHAT_NODES = frozenset(
    {
        "chat_simple",
        "chat_analytical",
        "chat_deep",
        "chat_router",
        # legacy names (models.yaml pre-rename)
        "slack_chat_simple",
        "slack_chat_analytical",
        "slack_chat_deep",
        "slack_router",
    }
)


def invoke_node_llm(
    node: str,
    system: str,
    user: str,
    tracker: CostTracker | None = None,
) -> str:
    tracker = tracker or get_active_tracker()
    if node in _CHAT_NODES or node.startswith("chat_") or node.startswith("slack_chat"):
        tracker.check_chat_budget()
    else:
        tracker.check_brief_budget()
    llm, model_id, _ = build_chat_model(node)
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    response = llm.invoke(messages)
    content = response.content
    if isinstance(content, list):
        content = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    meta = getattr(response, "usage_metadata", None) or {}
    tracker.record(
        node=node,
        model=model_id,
        input_tokens=int(meta.get("input_tokens", 0) or len(system + user) // 4),
        output_tokens=int(meta.get("output_tokens", 0) or len(str(content)) // 4),
    )
    return str(content)


def invoke_json_node(
    node: str,
    system: str,
    user: str,
    tracker: CostTracker | None = None,
) -> dict[str, Any]:
    text = invoke_node_llm(node, system, user, tracker)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
