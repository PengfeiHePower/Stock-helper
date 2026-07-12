# Stock Helper (Moka-chan)

[中文文档](README.zh-CN.md)

US equity personal assistant: collects news, runs a LangGraph multi-agent pipeline, and delivers briefs plus real-time alerts via **Telegram** and **email** (optional Slack).

## Features

### Briefs (3 sessions)

| Session | Schedule (ET) | Focus |
|---------|---------------|--------|
| **Morning** | 7:00 ET (trading days only) | Pre-market snapshot, macro/sectors/stocks, **watchlist earnings** (today + week), star IPOs |
| **Close** | 16:45 ET (trading days only) | Closing recap + **Since Pre-Market Brief** (macro score delta, new headlines, agent tracking changes, Morning vs Reality) |
| **Weekly** | Friday 17:30 ET (trading days only) | **Macro & tracking trends** (week path, agent adds), sector rotation, next-week earnings, look-ahead |

Scheduled briefs run only on **US trading days** (weekends and NYSE full holidays are skipped via Finnhub market calendar). Early-close days still get briefs.

All sessions share: LangGraph analysis (macro → sector → stocks → agent picks → risk), code-assembled markdown (no LLM truncation), HTML email + Telegram push.

Manual run: `stock-helper brief --session morning|close|weekly`  
Force on a weekend/holiday: `stock-helper brief --session morning --force`  
Check today: `stock-helper status` → `US trading day today: True/False`

### Brief structure

Each brief opens with **Moka-chan · …** title, date/session line, **macro score**, and a session greeting. Sections below are assembled in code (deterministic order; final body is not LLM-generated, so emails/Telegram are not truncated).

**Morning** — forward-looking, pre-open

| # | Section | Source |
|---|---------|--------|
| 1 | Pre-Market Snapshot | Core + ETF quotes (Finnhub) |
| 2 | Watchlist Earnings — Today & This Week | Finnhub calendar, watchlist tickers |
| 3 | Star IPO Radar | Finnhub IPO + `config/ipos.yaml` |
| 4 | Macro Backdrop for Today | FRED + headlines → LLM |
| 5 | Sectors to Watch | Headlines → LLM |
| 6 | Today's Focus — Stocks & ETFs | Per-ticker news → LLM |
| 7 | Also on Radar | Agent tracking list + headlines |
| 8 | Today's Risk Flags | LLM |
| — | Disclaimer | `config/persona.yaml` |

**Close** — recap vs pre-market

| # | Section | Source |
|---|---------|--------|
| 1 | **Since Pre-Market Brief** | Macro score delta, new headlines, agent tracking changes, **Morning vs Reality** (LLM vs morning brief) |
| 2 | Closing Snapshot | Core quotes |
| 3 | Up Next — Tonight & Tomorrow Pre-Market | Earnings (AMC / next-day BMO) |
| 4 | Star IPO Radar | Same as morning |
| 5 | Macro — Today's Take | LLM |
| 6 | Sector Recap | LLM |
| 7 | Stock Recap & Attribution | LLM |
| 8 | Agent Tracking — Today | Agent list |
| 9 | Surprises & Remaining Risks | LLM |

**Weekly** (Friday) — week in review + next week

| # | Section | Source |
|---|---------|--------|
| 1 | **This Week — Macro & Tracking** | DB: macro score path Mon→Fri, agent adds this week |
| 2 | Weekly Performance Snapshot | Core quotes |
| 3 | Next Week — Earnings Watch | 14-day calendar, next 7 days highlighted |
| 4 | Star IPO Radar | Same as daily |
| 5 | Macro — Week in Review | LLM |
| 6 | Sector Rotation This Week | LLM |
| 7 | Watchlist Weekly Recap | LLM |
| 8 | Agent Tracking — This Week | Agent list |
| 9 | Look Ahead & Risks | LLM |

Without LLM keys, template mode still includes snapshot, earnings, IPO, headlines, and agent list; LLM sections are omitted or stubbed.

### Data collection

- **Finnhub** — company/market news, quotes, earnings & IPO calendars
- **SEC EDGAR** — 8-K / 10-K / 10-Q for watchlist (requires `SEC_USER_AGENT`)
- **FRED** — optional macro series (requires `FRED_API_KEY`)
- **L1 classify** — tags news (`earnings`, `m_and_a`, …) when Gemini key is set
- **Template fallback** — quotes + headlines only when LLM keys are missing

### Watchlist & agent

- **`config/watchlist.yaml`** — `core` tickers, themed `lists`, agent tracking limits
- **Agent auto-tracking** — recommends tickers from news frequency; CLI/Telegram add/remove
- **Natural-language watchlist in chat** — e.g. `关注 AMD`, `不再关注 TSLA`, `follow NVDA` (agent tracking; core list stays in YAML)
- **Star IPO radar** — **`config/ipos.yaml`**: Finnhub calendar + manual watch list + large-deal filter

### Long-term analysis (monthly + biweekly)

**Market Reasoning Agent** (`stock_helper/reasoning/`) turns macro, structure, and sentiment facts into a **thesis-first** market view. Reports are split for readability:

| Layer | Audience | Content |
|-------|----------|---------|
| **Reader View** | Everyone | Market at a glance, what changed, takeaway, top 3 drivers, key tension, participation, narrative pulse, watch next, Moka explains |
| **Analyst Appendix** | Deep dive | Hypothesis tracking (HOLD/WEAKEN/INVALIDATED), evidence scores, causal graph, conflict machinery, raw headlines |

**Bilingual Reader View** — Chinese + English by default (`config/reasoning.yaml` → `reader_report.languages: [zh, en]`). Biweekly/monthly reports show **中文 first**, then `---`, then English. Set `[zh]` or `[en]` for a single language. Telegram chat `市场结构` / `市场故事` returns the **Chinese** Reader View when you write in Chinese.

| Report | Schedule (ET) | Focus |
|--------|---------------|--------|
| **Monthly** | First US trading day, 08:00 | Reader View + appendix + macro 4D, structure, sentiment, factors, strategy lenses, institutions |
| **Biweekly pulse** | First trading day on/after 1st & 15th, 08:15 | Compact Reader View + appendix (structure + sentiment; skips duplicate monthly sections) |

- **Macro dimensions:** inflation, growth, policy, risk (FRED rules)
- **Market structure:** breadth (RSP/SPY/IWM), QQQ vs SPY, sector rotation, Mag7, causal chains
- **Sentiment:** narrative topics, shift detection, competing hypotheses
- **Thesis:** evidence-derived (LLM thesis off by default — `thesis.use_llm: false`)

Commands:

```bash
stock-helper analyze              # monthly report (alias: monthly)
stock-helper analyze --refresh    # force refresh fundamentals
stock-helper biweekly             # biweekly pulse
```

Chat: `长期市场` / `长期分析 NVDA` / `L3 看 AMD` (monthly cache) · `市场结构` / `市场故事` / `thesis` (Reader View)

Details: [docs/ANALYSIS.md](docs/ANALYSIS.md)

### CIO Strategy Layer (allocation recommendations)

**Analysis ≠ advice.** The CIO Agent follows an **Investment Decision Pipeline** (v2):

```
Regime → Theme → Industry → Stock → Portfolio → Scenario → Triggers → Monitor
```

Each layer uses **Evidence → Hypothesis → Counter → Decision** reasoning. **US equities only.**

| Layer | Output |
|-------|--------|
| 1 Regime | Market state, narrative, key conflict (no trades yet) |
| 2 Theme | ★-rated themes (AI Infrastructure, Defense, …) |
| 3 Industry | GPU, Memory, Networking under themes |
| 4 Stock | Ranked names by industry with bull/bear case |
| 5 Portfolio | Strategic allocation + active tilts + ETF/stock sleeve |
| 6–8 | Scenarios, If→Then triggers, health dashboard + watch list |

```bash
stock-helper strategy
stock-helper strategy --level L1
```

Chat: `投资策略` / `资产配置` / `CIO`

Config: `config/cio.yaml` · Details: [docs/STRATEGY.md](docs/STRATEGY.md)

### Real-time alerts

- **`config/alerts.yaml`** — polled by the **schedule** process (not the chat bot)
- Telegram pings on: SEC filings, material headlines, watchlist **price moves** (per-symbol rules, no LLM)
- Defaults: 10 min price poll, 30 min news ingest, skips duplicate ingest after brief runs
- **Not limited to trading days** — polls every day in the configured time window (default 07:00–20:00 ET)

### Telegram (brief + chat)

- Scheduled briefs posted to `TELEGRAM_CHAT_ID`
- **Moka-chan** chat bot (`stock-helper telegram`): Q&A on news/watchlist/brief, 中文/English (reply language follows **current message**), **persistent chat memory** (SQLite)
- Commands: `/start`, `/watchlist`, `/track TICKER`, `/untrack TICKER`
- **Groups:** @mention the bot, reply to its message, or `/command@botname`; private chat needs no @. Bot must be allowed to **send messages** in the group (admin not required unless the group restricts members).

See [docs/TELEGRAM.md](docs/TELEGRAM.md) for BotFather setup.

### LLM, persona & cost

- **Plan A** — Gemini Flash-Lite (L1) + Claude Sonnet (L2/L3); routing in **`config/models.yaml`**
- **Persona** — **`config/persona.yaml`**: Moka-chan voice (lively tone, factual content)
- **Cost tracker** — per-run budgets, logged to SQLite

### Other outputs

- **Email** — full HTML brief via Resend (`RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_TO`)
- **Slack** — optional Socket Mode bot + brief channel (`SLACK_*`)

---

## Setup (Conda)

Requires **Python 3.12+**.

```bash
cd stock_helper
conda activate stock
pip install -e .

cp .env.example .env
# Fill in API keys — see Configuration below
```

| Key | Purpose |
|-----|---------|
| `FINNHUB_API_KEY` | News, quotes, earnings/IPO calendars |
| `GOOGLE_API_KEY` | L1 (Gemini classify + simple chat) |
| `ANTHROPIC_API_KEY` | L2/L3 (brief agents + analytical chat) |
| `FRED_API_KEY` | Optional macro data in brief |
| `SEC_USER_AGENT` | Required for SEC; **use your real email** |
| `RESEND_API_KEY` + `EMAIL_FROM` + `EMAIL_TO` | Email briefs |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Brief push, alerts, chat |
| `SLACK_*` | Optional Slack |
| `BRIEF_TIMEZONE` | Scheduler timezone (default `America/New_York`) |
| `DATABASE_URL` | SQLite path (default `data/stock_helper.db`) |

---

## Commands

```bash
stock-helper status                              # config + DB stats + US trading day today
stock-helper ingest                              # fetch watchlist news (respects ingest cooldown when chained)

stock-helper brief --session morning             # full pipeline + deliver (skipped on non-trading days)
stock-helper brief --session close
stock-helper brief --session weekly
stock-helper brief --session morning --force     # run even on weekend/holiday

stock-helper watchlist show
stock-helper watchlist track NVDA
stock-helper watchlist untrack NVDA
stock-helper watchlist recommend                 # show suggestions
stock-helper watchlist recommend --apply         # auto-add recommendations

stock-helper alerts                              # one alert poll (test; bypasses market-hours window)
stock-helper schedule                            # blocking scheduler (briefs + alerts)
stock-helper telegram                            # chat bot (long polling)
stock-helper slack                               # optional Slack bot

stock-helper analyze                             # monthly market & strategy report
stock-helper analyze --refresh                   # force refresh Finnhub fundamentals
stock-helper biweekly                            # biweekly market pulse (Reader View)
stock-helper strategy                            # CIO strategy recommendation
stock-helper strategy --level L1                 # conservative allocation profile
```

### Background (recommended)

```bash
./scripts/start.sh      # schedule + telegram
./scripts/status.sh
./scripts/stop.sh
```

Logs: `logs/schedule.log`, `logs/telegram.log`

---

## Configuration

YAML files live in `config/`. After editing, restart `./scripts/stop.sh && ./scripts/start.sh` for schedule/Telegram. `stock-helper brief` reloads YAML on each run.

### `.env`

Secrets and paths — see Setup table. Run `stock-helper status` to see which keys are configured.

### `config/watchlist.yaml`

```yaml
core: [AAPL, MSFT, ...]       # Brief focus + news ingest
lists:
  ai_infra: [...]             # Themed groups (also ingested)
  etfs: [SPY, QQQ, SMH]       # Extra quotes in morning snapshot
agent_tracking:
  enabled: true
  max_size: 15
  auto_expire_days: 14
```

Manage agent list: natural language in chat (`关注 AMD` / `follow NVDA`), Telegram `/track` & `/untrack`, or `stock-helper watchlist` subcommands. Core tickers in `core:` are fixed in YAML.

### `config/alerts.yaml`

| Key | Default | Meaning |
|-----|---------|---------|
| `enabled` | `true` | Master switch |
| `poll_interval_minutes` | `10` | Price check interval (Finnhub `/quote`) |
| `news_ingest_every_n_polls` | `3` | Ingest every N polls → **30 min** at default |
| `skip_ingest_if_ran_within_minutes` | `30` | Skip alert ingest after brief/CLI ingest |
| `market_hours` | 07:00–20:00 ET, every day | Alert polling window (not limited to US trading days) |
| `price.default_move_pct` | `5.0` | Default daily move threshold (%) |
| `price.rules[]` | e.g. NVDA 3%, VIX 8% up | Per-symbol overrides |

News alerts: SEC forms, material keywords, or L1 types (`earnings`, `m_and_a`, `legal`).

Tune sensitivity: `poll_interval_minutes: 5`, `news_ingest_every_n_polls: 2`.  
Save API: `poll_interval_minutes: 15`, `news_ingest_every_n_polls: 4`.

### `config/ipos.yaml`

| Key | Meaning |
|-----|---------|
| `enabled` | IPO section in brief |
| `lookahead_days` | Calendar horizon |
| `min_deal_value_usd` | Auto-flag large deals (e.g. 300000000) |
| `auto_notable` | Include large deals not on `watch` |
| `watch` | Names/tickers to always highlight |

### `config/persona.yaml`

| Key | Meaning |
|-----|---------|
| `name` / `display_name` | Moka-chan branding |
| `brief_system` / `chat_system` | LLM prompts (`{name}` placeholder) |
| `brief_greeting` | `morning` / `close` / `weekly` openers |
| `chat_greeting` | Telegram `/start` text |
| `chat_intro` | Short canned self-intro (no brief dump) |
| `disclaimer` | Brief footer |

Chat language matching and tone rules live in `chat_system`.

### `config/models.yaml`

| Section | Meaning |
|---------|---------|
| `tiers.l1/l2/l3` | Models, temperature, max tokens |
| `node_models` | Which agent node uses which tier (`chat_simple` / `chat_analytical` / `chat_deep` for Q&A) |
| `node_overrides` | Per-node `max_tokens` etc. (e.g. chat replies) |
| `budget.*` | Daily brief, chat session (`chat_session_max_usd`), and monthly USD caps |

### `config/analysis.yaml`

Long-horizon analysis scheduling and scope.

| Key | Meaning |
|-----|---------|
| `monthly_report` | First trading day of month, default 08:00 ET |
| `biweekly_update` | First trading day on/after 1st & 15th, default 08:15 ET |
| `default_risk_level` | L1 / L2 / L3 portfolio template |
| `data_refresh.fundamentals_max_age_days` | Finnhub fundamentals cache TTL |

### `config/reasoning.yaml`

Market Reasoning Agent rules and Reader View output.

| Key | Meaning |
|-----|---------|
| `reader_report.languages` | `[zh, en]` bilingual (zh first), `[zh]` Chinese only, or `[en]` English only |
| `thesis.use_llm` | `false` = evidence-derived thesis (default); `true` = optional LLM thesis |
| `drivers.*` / `hypotheses.*` | Driver weights and hypothesis priors |

### `config/strategy.yaml`

CIO Strategy Layer — allocation templates, sector/style tilts, position sizing, risk posture.

| Key | Meaning |
|-----|---------|
| `regime_templates` | Base asset-class weights per macro regime |
| `risk_level_tilt` | L1/L2/L3 equity multipliers |
| `cio_report.languages` | `[zh, en]` bilingual CIO section |
| `position_sizing` | Core ETF, max satellite names, lens score floor |

---

## Scheduled jobs (ET, `BRIEF_TIMEZONE`)

| Time | Job |
|------|-----|
| 7:00 | Morning brief + ingest — **US trading days only** |
| 16:45 | Close brief + ingest — **US trading days only** |
| 17:30 Friday | Weekly wrap — **US trading days only** (skipped if Friday is a holiday) |
| 08:00, 1st trading day of month | Monthly market & strategy report — **US trading days only** |
| 08:15, 1st trading day on/after 1st & 15th | Biweekly market pulse — **US trading days only** (skipped when monthly runs same day) |
| Every `poll_interval_minutes`, 07:00–20:00 **every day** | Price alerts; periodic news ingest |

Trading-day check uses Finnhub `/stock/market-holiday` (cached 24h). Without `FINNHUB_API_KEY`, only weekends are skipped.

Brief runs always ingest once; alert polling skips ingest for `skip_ingest_if_ran_within_minutes` afterward.

---

## Disclaimer

For informational purposes only. Not investment advice.
