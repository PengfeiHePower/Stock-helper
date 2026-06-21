# Telegram Setup for Stock Helper

Telegram is **free** for personal bots: no paid channels, no business verification (unlike WhatsApp Business API).

Stock Helper uses Telegram for:

1. **Daily brief push** — when you run `stock-helper brief` or `schedule`
2. **Conversational Q&A** — when you run `stock-helper telegram`

---

## Step 1: Create a bot (BotFather)

1. Open Telegram and search **@BotFather**
2. Send `/newbot`
3. Choose a display name, e.g. `Stock Helper`
4. Choose a username ending in `bot`, e.g. `pengfei_stock_bot`
5. BotFather replies with a token like:

   ```
   7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

6. Add to `.env`:

   ```env
   TELEGRAM_BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

## Step 2: Get your Chat ID

The bot needs to know **where to send** the daily brief (your private chat).

1. Start the bot locally:

   ```bash
   conda activate stock
   cd stock_helper
   stock-helper telegram
   ```

2. In Telegram, open your new bot and send:

   ```
   /start
   ```

3. The bot replies with help text and a line like:

   ```
   Your chat id: 123456789
   Set TELEGRAM_CHAT_ID=123456789 in .env
   ```

4. Add to `.env`:

   ```env
   TELEGRAM_CHAT_ID=123456789
   ```

5. Restart `stock-helper telegram` (or just run brief — push does not require the bot process).

**Alternative:** message [@userinfobot](https://t.me/userinfobot) — it shows your numeric user id (same as chat id for private chats).

---

## Step 3: Verify

```bash
stock-helper status
```

Expect:

```
telegram_bot: ok
telegram_brief: ok
```

Test brief push:

```bash
stock-helper brief --session morning
# → Telegram brief posted
```

Check Telegram — you should receive the full brief (split into multiple messages if long).

---

## Step 4: Daily usage

| What | Command | Notes |
|------|---------|-------|
| Push brief | `stock-helper brief` | Also sends email |
| Auto schedule | `stock-helper schedule` | 7:00 & 16:45 US/Eastern |
| Chat bot | `stock-helper telegram` | Must stay running |

Run the chat bot in the background:

```bash
nohup stock-helper telegram > logs/telegram.log 2>&1 &
# or tmux / screen
```

---

## Bot commands

| Command | Action |
|---------|--------|
| `/start` | Help + show your chat id |
| `/help` | Same as start |
| `/watchlist` | Show core + agent tracking lists |
| `/track NVDA` | Add ticker to agent tracking |
| `/untrack NVDA` | Remove ticker |
| Free text | Ask about stocks, news, macro, etc. |

Examples:

```
NVDA news today?
Why is the macro score negative?
Compare AAPL and MSFT risk
```

---

## Brief vs Email

| Channel | Format | Length |
|---------|--------|--------|
| **Email** | HTML tables, bold, full layout | Complete |
| **Telegram** | Plain text, split messages | Full content (up to 4096 chars per message) |

Email remains the best reading experience; Telegram is great for mobile alerts and chat.

---

## Optional: Telegram group or channel

By default, `TELEGRAM_CHAT_ID` is **your private chat** with the bot.

To post briefs to a **group**:

1. Add your bot to the group
2. Send a message in the group
3. Visit (replace `TOKEN`):

   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

4. Find `"chat":{"id":-100xxxxxxxxxx}` for the group (negative id)
5. Set `TELEGRAM_CHAT_ID=-100xxxxxxxxxx`

For a **channel**, add the bot as admin, use the channel chat id the same way.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Unauthorized` | Wrong `TELEGRAM_BOT_TOKEN` |
| Brief not arriving | Set `TELEGRAM_CHAT_ID`; send `/start` to bot first |
| Bot not replying | Is `stock-helper telegram` running? |
| `chat not found` | Wrong chat id; use `/start` to get the correct one |
| Two bot instances | Only one `getUpdates` poll per token — stop duplicate processes |

---

## Slack vs Telegram (this project)

You can use **both**, **Telegram only**, or **email + Telegram**:

- Leave `SLACK_*` empty in `.env` if you skip Slack
- Telegram does not require creating a paid Slack channel
