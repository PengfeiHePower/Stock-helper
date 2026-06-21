from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_api_key: str = ""
    anthropic_api_key: str = ""
    finnhub_api_key: str = ""
    fred_api_key: str = ""
    resend_api_key: str = ""
    email_from: str = "brief@example.com"
    email_to: str = ""
    slack_bot_token: str = ""
    slack_app_token: str = ""
    slack_brief_channel: str = "#stock-brief"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    sec_user_agent: str = "StockHelper contact@example.com"
    database_url: str = f"sqlite:///{ROOT / 'data' / 'stock_helper.db'}"
    brief_timezone: str = "America/New_York"

    config_dir: Path = Field(default=CONFIG_DIR)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_yaml(name: str) -> dict[str, Any]:
    path = get_settings().config_dir / name
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def has_llm_keys(l1: bool = False, l2: bool = False) -> bool:
    s = get_settings()
    if l1 and not l2:
        return bool(s.google_api_key)
    if l2 and not l1:
        return bool(s.anthropic_api_key)
    return bool(s.google_api_key and s.anthropic_api_key)


PLACEHOLDER_MARKERS = ("...", "xxx", "your_", "example.com", "you@example", "changeme")


def is_env_set(value: str, *, prefixes: tuple[str, ...] = ()) -> bool:
    """True only when value looks like a real secret, not an empty or example placeholder."""
    v = (value or "").strip()
    if not v or len(v) < 8:
        return False
    lower = v.lower()
    if any(m in lower for m in PLACEHOLDER_MARKERS):
        return False
    if prefixes and not any(v.startswith(p) for p in prefixes):
        return False
    return True


def config_status() -> dict[str, bool]:
    s = get_settings()
    return {
        "finnhub": is_env_set(s.finnhub_api_key),
        "fred": is_env_set(s.fred_api_key),
        "google_l1": is_env_set(s.google_api_key),
        "anthropic_l2": is_env_set(s.anthropic_api_key),
        "email": is_env_set(s.resend_api_key) and is_env_set(s.email_to, prefixes=("@",)),
        "slack_bot": is_env_set(s.slack_bot_token, prefixes=("xoxb-",)),
        "slack_socket": is_env_set(s.slack_app_token, prefixes=("xapp-",)),
        "telegram_bot": is_env_set(s.telegram_bot_token) and ":" in s.telegram_bot_token,
        "telegram_brief": (
            is_env_set(s.telegram_bot_token)
            and s.telegram_chat_id.strip().lstrip("-").isdigit()
        ),
    }


def slack_configured() -> bool:
    s = get_settings()
    return is_env_set(s.slack_bot_token, prefixes=("xoxb-",)) and bool(
        s.slack_brief_channel.strip()
    )


def telegram_brief_configured() -> bool:
    s = get_settings()
    return bool(config_status()["telegram_brief"])
