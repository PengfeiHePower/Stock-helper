from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from stock_helper.agents.chat import (
    format_watchlist_summary,
    handle_watchlist_command,
    slack_chat,
)
from stock_helper.agents.persona import chat_greeting
from stock_helper.config import get_settings
from stock_helper.outputs.brief_renderer import (
    brief_to_telegram_messages,
    markdown_to_telegram_html,
    split_text_chunks,
)

logger = logging.getLogger(__name__)

TELEGRAM_MAX_MESSAGE = 4096


class TelegramClient:
    def __init__(self, token: str | None = None):
        self.token = token or get_settings().telegram_bot_token
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")
        self.base = f"https://api.telegram.org/bot{self.token}"

    def _post(self, method: str, payload: dict[str, Any]) -> dict:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{self.base}/{method}", json=payload)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(data.get("description", "Telegram API error"))
            return data

    def send_message(
        self,
        chat_id: str | int,
        text: str,
        parse_mode: str | None = None,
    ) -> dict:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return self._post("sendMessage", payload)

    def get_updates(self, offset: int | None = None, timeout: int = 30) -> list[dict]:
        payload: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        data = self._post("getUpdates", payload)
        return data.get("result", [])


def post_brief_to_telegram(brief_md: str, session: str) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured")

    client = TelegramClient()
    chat_id = settings.telegram_chat_id
    messages = brief_to_telegram_messages(brief_md, session)

    for msg in messages:
        client.send_message(chat_id, msg, parse_mode="HTML")


HELP_TEXT = chat_greeting() + """

Commands~
/start — help + your chat id
/watchlist — show watchlists
/track TICKER — add to agent tracking
/untrack TICKER — remove from agent tracking

Try asking:
• NVDA news today?
• Why is macro score negative?"""


def _handle_command(text: str) -> str | None:
    stripped = text.strip()
    lower = stripped.lower()

    if lower in ("/start", "/help"):
        return HELP_TEXT

    if lower == "/watchlist":
        return format_watchlist_summary().replace("*", "")

    if lower.startswith("/track "):
        return handle_watchlist_command(f"track {stripped.split(maxsplit=1)[1]}")

    if lower.startswith("/untrack "):
        return handle_watchlist_command(f"untrack {stripped.split(maxsplit=1)[1]}")

    return None


def run_telegram_bot() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")

    client = TelegramClient()
    chat_memory: dict[int, str] = {}
    offset: int | None = None

    print("Telegram bot running (Ctrl+C to stop)...")
    print("Message your bot on Telegram to start.")

    while True:
        try:
            updates = client.get_updates(offset=offset, timeout=30)
        except httpx.HTTPError as e:
            logger.warning("Telegram poll error: %s", e)
            time.sleep(5)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message") or update.get("edited_message")
            if not message or "text" not in message:
                continue

            chat_id = message["chat"]["id"]
            text = message["text"].strip()
            if not text:
                continue

            cmd_reply = _handle_command(text)
            if cmd_reply:
                if text.lower().startswith("/start"):
                    cmd_reply += (
                        f"\n\nYour chat id: {chat_id}"
                        f"\nAdd to .env: TELEGRAM_CHAT_ID={chat_id}"
                    )
                try:
                    client.send_message(chat_id, cmd_reply)
                except httpx.HTTPError as e:
                    logger.warning("Failed to send command reply: %s", e)
                continue

            ctx = chat_memory.get(chat_id, "")
            reply = slack_chat(text, thread_context=ctx)
            chat_memory[chat_id] = f"{ctx}\nUser: {text}\nAssistant: {reply}"[-4000:]

            reply_html = markdown_to_telegram_html(reply)
            for chunk in split_text_chunks(reply_html, max_len=TELEGRAM_MAX_MESSAGE):
                try:
                    client.send_message(chat_id, chunk, parse_mode="HTML")
                except httpx.HTTPError as e:
                    logger.warning("Failed to send reply chunk: %s", e)
                    break
