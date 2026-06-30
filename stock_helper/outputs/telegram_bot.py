from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from stock_helper.agents.chat import (
    format_watchlist_summary,
    handle_watchlist_command,
    chat_reply,
)
from stock_helper.agents.persona import chat_greeting
from stock_helper.config import get_settings
from stock_helper.storage.db import get_chat_context, save_chat_context
from stock_helper.outputs.brief_renderer import (
    brief_to_telegram_messages,
    markdown_to_telegram_html,
    split_text_chunks,
)

logger = logging.getLogger(__name__)

TELEGRAM_MAX_MESSAGE = 4096
TELEGRAM_CHUNK = 3800


GROUP_CHAT_TYPES = frozenset({"group", "supergroup"})


def is_group_chat(chat: dict) -> bool:
    return chat.get("type") in GROUP_CHAT_TYPES


def bot_is_addressed(message: dict, bot_id: int, bot_username: str) -> bool:
    """True when the user intentionally invoked this bot."""
    text = message.get("text", "")
    if text.startswith("/"):
        command = text.split(maxsplit=1)[0]
        if "@" not in command:
            return True
        return command.split("@", 1)[1].lower() == bot_username.lower()

    for ent in message.get("entities") or []:
        if ent["type"] == "mention":
            mention = text[ent["offset"] : ent["offset"] + ent["length"]]
            if mention.lstrip("@").lower() == bot_username.lower():
                return True
        if ent["type"] == "text_mention":
            user = ent.get("user") or {}
            if user.get("id") == bot_id:
                return True

    reply = message.get("reply_to_message") or {}
    from_user = reply.get("from") or {}
    return from_user.get("id") == bot_id


def normalize_group_text(text: str, bot_username: str) -> str:
    """Remove @bot suffix from commands and @mentions from free text."""
    if text.startswith("/"):
        parts = text.split(maxsplit=1)
        command = parts[0]
        suffix = f"@{bot_username}"
        if command.lower().endswith(suffix.lower()):
            command = command[: -len(suffix)]
        if len(parts) > 1:
            return f"{command} {parts[1]}".strip()
        return command

    mention = f"@{bot_username}"
    cleaned = text
    for variant in (mention, mention.lower()):
        cleaned = cleaned.replace(variant, "")
    return cleaned.strip()


def _safe_send(
    client: TelegramClient,
    chat_id: str | int,
    text: str,
    parse_mode: str | None = None,
) -> bool:
    try:
        client.send_message(chat_id, text, parse_mode=parse_mode)
        return True
    except (httpx.HTTPError, RuntimeError) as e:
        logger.warning("Telegram send failed (chat=%s): %s", chat_id, e)
        return False


def _send_chat_reply(client: TelegramClient, chat_id: str | int, reply: str) -> None:
    """Split plain markdown first, then HTML per chunk; fallback to plain text."""
    chunks = split_text_chunks(reply.strip(), max_len=TELEGRAM_CHUNK)
    if not chunks:
        return

    for i, chunk in enumerate(chunks):
        chunk_body = f"({i + 1}/{len(chunks)})\n\n{chunk}" if len(chunks) > 1 else chunk
        html = markdown_to_telegram_html(chunk_body)
        if _safe_send(client, chat_id, html, parse_mode="HTML"):
            continue
        if not _safe_send(client, chat_id, chunk_body):
            break


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

    def get_me(self) -> dict:
        return self._post("getMe", {})["result"]

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
• 关注 AMD / 不再关注 TSLA
• follow INTC / unfollow INTC
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


def _process_message(
    client: TelegramClient,
    message: dict,
    bot_id: int,
    bot_username: str,
) -> None:
    chat = message["chat"]
    chat_id = chat["id"]
    text = message["text"].strip()
    if not text:
        return

    in_group = is_group_chat(chat)
    if in_group and not bot_is_addressed(message, bot_id, bot_username):
        logger.debug("Skipping group message not addressed to bot (chat=%s)", chat_id)
        return

    if in_group:
        text = normalize_group_text(text, bot_username)
        if not text:
            return

    cmd_reply = _handle_command(text)
    if cmd_reply:
        if text.lower().startswith("/start"):
            cmd_reply += (
                f"\n\nYour chat id: {chat_id}"
                f"\nAdd to .env: TELEGRAM_CHAT_ID={chat_id}"
            )
        _safe_send(client, chat_id, cmd_reply)
        return

    ctx = get_chat_context(chat_id)
    try:
        reply = chat_reply(text, thread_context=ctx)
    except Exception:
        logger.exception("Chat handler failed (chat=%s)", chat_id)
        _safe_send(
            client,
            chat_id,
            "Sorry, something went wrong processing your message. Please try again.",
        )
        return

    save_chat_context(
        chat_id,
        f"{ctx}\nUser: {text}\nAssistant: {reply}",
    )
    _send_chat_reply(client, chat_id, reply)


def run_telegram_bot() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")

    client = TelegramClient()
    me = client.get_me()
    bot_id = me["id"]
    bot_username = me["username"]
    offset: int | None = None

    print("Telegram bot running (Ctrl+C to stop)...")
    print(f"Bot: @{bot_username} (id {bot_id})")
    print("Private chat: message directly. Groups: @mention the bot or reply to it.")

    while True:
        try:
            updates = client.get_updates(offset=offset, timeout=30)
        except (httpx.HTTPError, RuntimeError) as e:
            logger.warning("Telegram poll error: %s", e)
            time.sleep(5)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message") or update.get("edited_message")
            if not message or "text" not in message:
                continue

            try:
                _process_message(client, message, bot_id, bot_username)
            except Exception:
                logger.exception(
                    "Unhandled error processing update %s",
                    update.get("update_id"),
                )
