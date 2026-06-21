# Stock Helper

US equity personal assistant: collects news, runs LangGraph multi-agent analysis, delivers a daily brief via **email** and **Telegram**, with optional Slack support.

## Features

- **Watchlist** (`config/watchlist.yaml`): core tickers, themed lists, agent tracking
- **Star IPO radar** (`config/ipos.yaml`): Finnhub IPO calendar + manual watch list + large-deal filter
- **Real-time alerts** (`config/alerts.yaml`): SEC filings, material news, price moves → Telegram pings
- **Weekly wrap**: Friday 17:30 ET brief with macro trend + sector rotation recap
- **Collectors**: Finnhub news/quotes, SEC EDGAR filings, FRED macro (optional)
- **LangGraph pipeline**: market snapshot → macro → sector → stocks → agent picks → risk → final brief
- **Template fallback**: runs without LLM keys (quotes + headlines only)
- **Agent auto-tracking**: recommends tickers from news frequency
- **Plan A models**: Gemini Flash-Lite (L1) + Claude Sonnet (L2/L3) with per-node routing
- **Cost tracker**: budget caps in `config/models.yaml`, logged to SQLite
- **Outputs**: Resend email, Telegram bot, optional Slack
- **Persona** (`config/persona.yaml`): default voice is lively JK-style **Moka-chan** — professional data, playful tone

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
stock-helper brief --session close
stock-helper brief --session weekly
stock-helper alerts          # one-shot alert poll (test)
```

### Run schedule + Telegram bot (background)

```bash
./scripts/start.sh      # start both
./scripts/status.sh     # check processes + API config
./scripts/stop.sh       # stop both
```

Logs: `logs/schedule.log`, `logs/telegram.log`

Or run manually in tmux:

```bash
stock-helper schedule          # briefs 7:00 / 16:45 / Fri 17:30 ET + alert polling
stock-helper telegram          # conversational bot
```

## Configuration

All YAML configs live in `config/`. Edit files, then restart `./scripts/stop.sh && ./scripts/start.sh` (scheduler + Telegram bot reload on restart). Manual `stock-helper brief` picks up YAML immediately.

### `.env` — secrets & infrastructure

Copy from `.env.example`. Never commit `.env`.

| Variable | What to change |
|----------|----------------|
| `FINNHUB_API_KEY` | Required for quotes, news, earnings/IPO calendars |
| `GOOGLE_API_KEY` | L1 Gemini (news classify, simple chat) |
| `ANTHROPIC_API_KEY` | L2/L3 Sonnet (brief agents, deep chat) |
| `FRED_API_KEY` | Optional macro series in brief |
| `RESEND_API_KEY` + `EMAIL_FROM` + `EMAIL_TO` | Email brief delivery |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Brief push + alerts + chat bot |
| `SEC_USER_AGENT` | **Must include your real email** (SEC fair access) |
| `BRIEF_TIMEZONE` | Scheduler timezone (default `America/New_York`) |
| `DATABASE_URL` | SQLite path (default `data/stock_helper.db`) |

Check what is configured: `stock-helper status`

---

### `config/watchlist.yaml` — tickers & agent tracking

```yaml
core: [AAPL, MSFT, ...]       # Always in brief + default news ingest
lists:
  ai_infra: [...]             # Themed groups (also ingested)
  etfs: [SPY, QQQ, SMH]       # Added to morning quote snapshot
agent_tracking:
  enabled: true
  max_size: 15                # Cap auto/manual agent list
  auto_expire_days: 14        # Remove stale agent picks
```

**Common edits:** add/remove `core` tickers; create new `lists.*` themes; tune `max_size` / `auto_expire_days`.

Telegram/CLI: `/track TICKER`, `/untrack TICKER`, or `stock-helper watchlist track NVDA`

---

### `config/alerts.yaml` — real-time Telegram alerts

Runs inside the **schedule** process (not the Telegram chat bot). Default tuned to reduce Finnhub usage.

| Key | Default | Meaning |
|-----|---------|---------|
| `enabled` | `true` | Master switch for alert polling |
| `poll_interval_minutes` | `10` | How often to check **prices** (Finnhub `/quote` per symbol) |
| `news_ingest_every_n_polls` | `3` | Ingest news every N price polls → **30 min** at default |
| `skip_ingest_if_ran_within_minutes` | `30` | **Skip alert ingest** if brief/CLI just ingested (avoids 7:00 duplicate) |
| `market_hours.start` / `end` | `07:00`–`20:00` | ET window for polling (weekdays) |
| `price.default_move_pct` | `5.0` | Watchlist daily move alert threshold (%) |
| `price.rules[]` | NVDA 3%, SPY 2%, … | Per-symbol overrides; `direction: up` for VIX-only spikes |

**News alerts** fire on: SEC 8-K/10-K/10-Q, headline keywords (`earnings`, `merger`, …), or L1-classified types (`earnings`, `m_and_a`, `legal`).

**More sensitive:** lower `poll_interval_minutes` to `5`, set `news_ingest_every_n_polls: 2` (10 min ingest).  
**Save API calls:** raise poll to `15`, ingest every `4` polls (60 min), or set `skip_ingest_if_ran_within_minutes: 45`.

Test: `stock-helper alerts` (one manual cycle; `force` bypasses market-hours check but still respects ingest cooldown unless brief ran &lt;30 min ago).

---

### `config/ipos.yaml` — star IPO radar (in brief)

| Key | Meaning |
|-----|---------|
| `enabled` | Show IPO section in brief |
| `lookahead_days` | Finnhub IPO calendar horizon |
| `min_deal_value_usd` | Auto-flag large deals (e.g. `300000000` = $300M+) |
| `auto_notable` | Include large deals even if not on `watch` list |
| `watch` | Company names/tickers to always highlight (substring match) |

Add rumored names (Stripe, Databricks, …); they appear once Finnhub lists them.

---

### `config/persona.yaml` — Moka-chan voice

| Key | Meaning |
|-----|---------|
| `name` / `display_name` | Bot name in briefs & greetings |
| `brief_system` / `chat_system` | LLM system prompts (`{name}` placeholder) |
| `brief_greeting.morning` / `close` / `weekly` | Opening line per session |
| `chat_greeting` | Telegram `/start` text |
| `disclaimer` | Footer on daily briefs |

Chat rules (language, no disclaimer spam) are in `chat_system`.

---

### `config/models.yaml` — LLM routing & budget

| Section | Meaning |
|---------|---------|
| `tiers.l1/l2/l3` | Model IDs, temperature, max tokens |
| `node_models` | Which brief/chat node uses which tier |
| `budget.daily_brief_max_usd` | Cap per brief run |
| `budget.slack_session_max_usd` | Cap per Telegram/chat session turn |
| `budget.monthly_max_usd` | Monthly total cap |

Lower `daily_brief_max_usd` to force cheaper/shorter outputs; map heavy nodes to `l1` to save cost (quality trade-off).

---

### Scheduled jobs (ET, `BRIEF_TIMEZONE`)

| Time | Job |
|------|-----|
| 7:00 weekdays | Morning brief + ingest |
| 16:45 weekdays | Close brief + ingest |
| 17:30 Friday | Weekly wrap |
| Every `poll_interval_minutes` (7:00–20:00 weekdays) | Price alerts; news ingest per `alerts.yaml` |

Morning/close briefs always ingest once; alert polling **skips ingest** for 30 minutes afterward so 7:00 / 16:45 are not doubled.

---

## Telegram setup

See [docs/TELEGRAM.md](docs/TELEGRAM.md) for step-by-step BotFather setup.

Quick version:

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy token → `TELEGRAM_BOT_TOKEN`
2. Run `stock-helper telegram`, message your bot `/start` → copy chat id → `TELEGRAM_CHAT_ID`
3. `stock-helper brief` posts the daily brief to that chat

## Disclaimer

For informational purposes only. Not investment advice.
