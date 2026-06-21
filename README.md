# Stock Helper

US equity personal assistant: collects news, runs LangGraph multi-agent analysis, delivers a daily brief via **email** and **Telegram**, with optional Slack support.

## Features

- **Watchlist** (`config/watchlist.yaml`): core tickers, themed lists, agent tracking
- **Collectors**: Finnhub news/quotes, SEC EDGAR filings, FRED macro (optional)
- **LangGraph pipeline**: market snapshot → macro → sector → stocks → agent picks → risk → final brief
- **Template fallback**: runs without LLM keys (quotes + headlines only)
- **Agent auto-tracking**: recommends tickers from news frequency
- **Plan A models**: Gemini Flash-Lite (L1) + Claude Sonnet (L2/L3) with per-node routing
- **Cost tracker**: budget caps in `config/models.yaml`, logged to SQLite
- **Outputs**: Resend email, Telegram bot, optional Slack

## Setup (Conda)

Requires **Python 3.12+** (LangGraph + Pydantic TypedDict state works reliably on 3.12).

```bash
cd stock_helper
conda activate stock
pip install -e .

cp .env.example .env
# Fill in API keys
```

| Key | Purpose |
|-----|---------|
| `FINNHUB_API_KEY` | News & quotes |
| `GOOGLE_API_KEY` | L1 (Gemini) |
| `ANTHROPIC_API_KEY` | L2/L3 (Sonnet) |
| `RESEND_API_KEY` + `EMAIL_TO` | Daily email (full brief) |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Telegram brief + chat |
| `SLACK_*` | Optional Slack |

## Commands

```bash
stock-helper status
stock-helper brief --session morning
stock-helper telegram          # conversational bot (keep running)
stock-helper schedule          # timed brief → email + telegram
```

## Telegram setup

See [docs/TELEGRAM.md](docs/TELEGRAM.md) for step-by-step BotFather setup.

Quick version:

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy token → `TELEGRAM_BOT_TOKEN`
2. Run `stock-helper telegram`, message your bot `/start` → copy chat id → `TELEGRAM_CHAT_ID`
3. `stock-helper brief` posts the daily brief to that chat

## Disclaimer

For informational purposes only. Not investment advice.
