from __future__ import annotations

from stock_helper.agents.chat import handle_watchlist_command, slack_chat
from stock_helper.config import get_settings


def post_brief_to_slack(brief_md: str, session: str) -> None:
    settings = get_settings()
    if not settings.slack_bot_token:
        raise RuntimeError("SLACK_BOT_TOKEN not configured")

    from slack_sdk import WebClient

    client = WebClient(token=settings.slack_bot_token)
    channel = settings.slack_brief_channel
    preview = brief_md[:3900] + ("..." if len(brief_md) > 3900 else "")
    client.chat_postMessage(
        channel=channel,
        text=f"*Stock Helper Daily Brief* ({session})\n\n{preview}",
        mrkdwn=True,
    )


def create_slack_app():
    settings = get_settings()
    if not settings.slack_bot_token:
        raise RuntimeError("SLACK_BOT_TOKEN not configured")

    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    app = App(token=settings.slack_bot_token)
    thread_memory: dict[str, str] = {}

    @app.event("app_mention")
    def on_mention(event, say, logger):
        text = event.get("text", "")
        parts = text.split(">", 1)
        user_msg = parts[-1].strip() if parts else text
        thread_ts = event.get("thread_ts") or event.get("ts")

        wl_reply = handle_watchlist_command(user_msg)
        if wl_reply:
            say(wl_reply, thread_ts=thread_ts)
            return

        ctx = thread_memory.get(thread_ts, "")
        reply = slack_chat(user_msg, thread_context=ctx)
        thread_memory[thread_ts] = (
            f"{ctx}\nUser: {user_msg}\nAssistant: {reply}"[-4000:]
        )
        say(reply, thread_ts=thread_ts)

    @app.message("")
    def on_dm(message, say, logger):
        if message.get("channel_type") != "im":
            return
        user_msg = message.get("text", "")
        wl_reply = handle_watchlist_command(user_msg)
        if wl_reply:
            say(wl_reply)
            return
        say(slack_chat(user_msg))

    app._socket_handler_cls = SocketModeHandler  # type: ignore[attr-defined]
    return app


def run_slack_socket_mode():
    settings = get_settings()
    app = create_slack_app()
    handler = app._socket_handler_cls(app, settings.slack_app_token)
    handler.start()
