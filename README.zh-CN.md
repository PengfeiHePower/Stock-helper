# Stock Helper (Moka-chan)

[English](README.md)

美股个人助手：采集新闻、运行 LangGraph 多 Agent 流水线，通过 **Telegram** 和**邮件**推送 brief，并支持实时 alert（可选 Slack）。

## 功能概览

### 三种 Brief

| 场次 | 时间（美东 ET） | 侧重点 |
|------|----------------|--------|
| **Morning 早报** | 美东 7:00（仅交易日） | 盘前快照、宏观/板块/个股、**watchlist 财报**（今日 + 本周）、明星 IPO |
| **Close 收盘** | 美东 16:45（仅交易日） | 收盘复盘 + **相对早报 diff**（宏观分数变化、新增 headline、agent 变动、Morning vs Reality） |
| **Weekly 周报** | 周五 17:30（仅交易日） | **宏观与 tracking 趋势**（本周路径、agent 新增）、板块轮动、下周财报、前瞻 |

定时 brief **只在美股交易日**发送（周末与 NYSE 全天休市节假日自动跳过，数据源为 Finnhub 节假日日历；提前收盘日仍会发）。

三种 brief 共用：LangGraph 分析链（macro → sector → stocks → agent picks → risk），**代码组装** markdown（避免 LLM 截断），HTML 邮件 + Telegram 推送。

手动运行：

```bash
stock-helper brief --session morning|close|weekly
stock-helper brief --session morning --force   # 周末/节假日强制跑
stock-helper status                            # 含「今天是否交易日」
```

### Brief 章节结构

每份 brief 开头为 **Moka-chan · …** 标题、日期/场次、**macro score** 与会话问候语。以下章节按固定顺序由代码组装（正文不由 LLM 一次性生成，邮件/Telegram 不会被截断）。

**Morning — 盘前前瞻**

| # | 章节 | 数据来源 |
|---|------|----------|
| 1 | Pre-Market Snapshot（盘前快照） | Core + ETF 报价（Finnhub） |
| 2 | Watchlist Earnings — Today & This Week | Finnhub 财报日历 |
| 3 | Star IPO Radar（明星 IPO） | Finnhub + `config/ipos.yaml` |
| 4 | Macro Backdrop for Today | FRED + 标题 → LLM |
| 5 | Sectors to Watch | 标题 → LLM |
| 6 | Today's Focus — Stocks & ETFs | 分 ticker 新闻 → LLM |
| 7 | Also on Radar | Agent tracking + 标题 |
| 8 | Today's Risk Flags | LLM |
| — | Disclaimer | `config/persona.yaml` |

**Close — 相对早报复盘**

| # | 章节 | 数据来源 |
|---|------|----------|
| 1 | **Since Pre-Market Brief** | 宏观分数 diff、新 headline、agent 变动、**Morning vs Reality**（对照早报 LLM 分析） |
| 2 | Closing Snapshot | Core 报价 |
| 3 | Up Next — Tonight & Tomorrow Pre-Market | 今晚 AMC / 明早 BMO 财报 |
| 4 | Star IPO Radar | 同早报 |
| 5 | Macro — Today's Take | LLM |
| 6 | Sector Recap | LLM |
| 7 | Stock Recap & Attribution | LLM |
| 8 | Agent Tracking — Today | Agent 列表 |
| 9 | Surprises & Remaining Risks | LLM |

**Weekly — 周五周报**

| # | 章节 | 数据来源 |
|---|------|----------|
| 1 | **This Week — Macro & Tracking** | DB：本周 macro 路径、agent 新增 |
| 2 | Weekly Performance Snapshot | Core 报价 |
| 3 | Next Week — Earnings Watch | 14 日日历，突出未来 7 天 |
| 4 | Star IPO Radar | 同日 brief |
| 5 | Macro — Week in Review | LLM |
| 6 | Sector Rotation This Week | LLM |
| 7 | Watchlist Weekly Recap | LLM |
| 8 | Agent Tracking — This Week | Agent 列表 |
| 9 | Look Ahead & Risks | LLM |

无 LLM Key 时进入 template 模式：仍有快照、财报、IPO、标题与 agent 列表；LLM 章节省略或占位。

### 数据采集

- **Finnhub** — 公司/市场新闻、报价、财报与 IPO 日历
- **SEC EDGAR** — watchlist 的 8-K / 10-K / 10-Q（需配置 `SEC_USER_AGENT`）
- **FRED** — 可选宏观序列（需 `FRED_API_KEY`）
- **L1 分类** — 有 Gemini Key 时为新闻打标签（`earnings`、`m_and_a` 等）
- **Template 回退** — 无 LLM Key 时仅报价 + 标题

### Watchlist 与 Agent

- **`config/watchlist.yaml`** — `core` 标的、主题 `lists`、agent tracking 上限
- **Agent 自动跟踪** — 按新闻频率推荐 ticker；CLI/Telegram 可增删
- **聊天自然语言改 watchlist** — 如「关注 AMD」「不再关注 TSLA」「follow NVDA」（改的是 agent tracking；`core` 列表仍在 YAML）
- **明星 IPO** — **`config/ipos.yaml`**：Finnhub 日历 + 手动 watch + 大额发行过滤

### 长期分析（月度 + 双周）

**Market Reasoning Agent**（`stock_helper/reasoning/`）把宏观、结构、情绪等事实整理成**以市场判断为核心**的报告。输出分两层，避免像调试日志：

| 层级 | 面向 | 内容 |
|------|------|------|
| **Reader View（读者版）** | 日常阅读 | 市场速览、变化、核心结论、三大驱动、核心矛盾、参与度、叙事脉搏、关注什么、Moka 白话 |
| **Analyst Appendix（分析师附录）** | 深挖 | 假设追踪（HOLD/WEAKEN/INVALIDATED）、证据分数、因果图、层间矛盾、原始标题 |

**中文版 Reader View** — 默认中英双语（`config/reasoning.yaml` → `reader_report.languages: [zh, en]`）。双周/月度报告**先中文**，`---` 分隔后再英文。可改为 `[zh]` 仅中文或 `[en]` 仅英文。Telegram 聊天发 `市场结构` / `市场故事`，用中文提问时返回**中文版** Reader View。

| 报告 | 时间（美东 ET） | 侧重点 |
|------|----------------|--------|
| **月度报告** | 每月第一个交易日 08:00 | Reader View + 附录 + 宏观四维、结构、情绪、因子、策略透镜、机构跟踪 |
| **双周脉搏** | 每月 1 日、15 日及之后首个交易日 08:15 | 精简 Reader View + 附录（结构 + 情绪；不重复月度长文） |

- **宏观四维：** 通胀、增长、政策、风险（FRED 规则）
- **市场结构：** 广度（RSP/SPY/IWM）、QQQ vs SPY、板块轮动、Mag7、因果链
- **情绪层：** 叙事主题、变化检测、竞争假设
- **市场判断：** 默认由证据推导（`thesis.use_llm: false`，不依赖 LLM 写 thesis）

命令：

```bash
stock-helper analyze              # 月度报告（同 monthly）
stock-helper analyze --refresh    # 强制刷新 Finnhub 基本面
stock-helper biweekly             # 双周脉搏
```

聊天：`长期市场` / `长期分析 NVDA` / `L3 看 AMD`（读月度缓存）· `市场结构` / `市场故事` / `thesis`（Reader View）

方法说明：[docs/ANALYSIS.md](docs/ANALYSIS.md)

### CIO 策略层（投资决策流水线 v2）

**分析 ≠ 投资建议。** CIO Agent 按 Buy-side 真实流程逐级缩小搜索空间：

```
市场阶段 → 主题 → 行业 → 个股 → 组合 → 情景 → 触发器 → 监控
```

每层均有 **证据 → 假设 → 反证 → 决策** 推理链。**仅美股。**

| 层级 | 输出 |
|------|------|
| 1 市场阶段 | 状态、叙事、核心矛盾（不给交易指令） |
| 2 主题轮动 | ★ 评级主题（AI 基础设施、国防等） |
| 3 行业轮动 | GPU、HBM、网络设备等 |
| 4 个股排序 | 按行业分组 + 多空逻辑 |
| 5 组合构建 | 战略配置 + 战术倾斜 + ETF/股票仓位 |
| 6–8 | 情景、If→Then 规则、健康度面板 + 关注日历 |

```bash
stock-helper strategy
stock-helper strategy --level L1
```

聊天：`投资策略` / `资产配置` / `CIO`

配置：`config/cio.yaml` · 详见 [docs/STRATEGY.md](docs/STRATEGY.md)

### 实时 Alert

- **`config/alerts.yaml`** — 由 **schedule** 进程轮询（**不是**聊天 bot）
- Telegram 推送：SEC 公告、重要 headline、watchlist **价格波动**（按 symbol 规则，不调 LLM）
- 默认：10 分钟查价、30 分钟 ingest 新闻；brief 跑完后跳过重复 ingest
- **不受交易日限制** — 每天在配置时段内轮询（默认美东 07:00–20:00，含周末与节假日）

### Telegram（推送 + 聊天）

- 定时 brief 发到 `TELEGRAM_CHAT_ID`
- **Moka-chan** 聊天 bot（`stock-helper telegram`）：新闻/watchlist/brief 问答，**中/英**回复（语言跟**当前这条消息**），**SQLite 持久对话记忆**
- 长期市场：`市场结构` / `市场故事` → 中文版 Reader View；`长期市场` → 月度缓存
- 命令：`/start`、`/watchlist`、`/track TICKER`、`/untrack TICKER`
- **群组：**需 `@` bot、回复 bot 消息，或 `/命令@bot名`；私聊直接发即可。群组里 bot 需有**发消息**权限（不必是 admin，除非群限制仅管理员发言）。

BotFather 配置详见 [docs/TELEGRAM.md](docs/TELEGRAM.md)（步骤说明为英文）。

### LLM、人设与成本

- **Plan A** — Gemini Flash-Lite（L1）+ Claude Sonnet（L2/L3）；路由见 **`config/models.yaml`**
- **Persona** — **`config/persona.yaml`**：Moka-chan 人设（活泼语气、内容严谨）
- **成本追踪** — 单次预算上限，记录于 SQLite

### 其他输出

- **邮件** — Resend 发送完整 HTML brief（`RESEND_API_KEY`、`EMAIL_FROM`、`EMAIL_TO`）
- **Slack** — 可选 Socket Mode bot + 频道（`SLACK_*`）

---

## 安装（Conda）

需要 **Python 3.12+**。

```bash
cd stock_helper
conda activate stock
pip install -e .

cp .env.example .env
# 填写 API Key — 见下方配置说明
```

| 变量 | 用途 |
|------|------|
| `FINNHUB_API_KEY` | 新闻、报价、财报/IPO 日历 |
| `GOOGLE_API_KEY` | L1（Gemini 分类 + 简单聊天） |
| `ANTHROPIC_API_KEY` | L2/L3（brief Agent + 深度聊天） |
| `FRED_API_KEY` | 可选，brief 宏观数据 |
| `SEC_USER_AGENT` | SEC 必填；**须含真实邮箱** |
| `RESEND_API_KEY` + `EMAIL_FROM` + `EMAIL_TO` | 邮件 brief |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | brief 推送、alert、聊天 |
| `SLACK_*` | 可选 Slack |
| `BRIEF_TIMEZONE` | 调度时区（默认 `America/New_York`） |
| `DATABASE_URL` | SQLite 路径（默认 `data/stock_helper.db`） |

---

## 命令

```bash
stock-helper status                              # 配置与 DB 统计 + 今天是否交易日
stock-helper ingest                              # 拉取 watchlist 新闻

stock-helper brief --session morning             # 完整流水线 + 推送（非交易日自动跳过）
stock-helper brief --session close
stock-helper brief --session weekly
stock-helper brief --session morning --force     # 周末/节假日强制运行

stock-helper watchlist show
stock-helper watchlist track NVDA
stock-helper watchlist untrack NVDA
stock-helper watchlist recommend                 # 查看推荐
stock-helper watchlist recommend --apply         # 自动加入推荐

stock-helper alerts                              # 手动跑一轮 alert（测试）
stock-helper schedule                            # 阻塞式调度（brief + alert）
stock-helper telegram                            # 聊天 bot
stock-helper slack                               # 可选 Slack bot

stock-helper analyze                             # 月度市场与策略报告
stock-helper analyze --refresh                   # 强制刷新 Finnhub 基本面
stock-helper biweekly                            # 双周市场脉搏（Reader View）
stock-helper strategy                            # CIO 投资策略建议
stock-helper strategy --level L1                 # 保守档位配置
```

### 后台运行（推荐）

```bash
./scripts/start.sh      # schedule + telegram
./scripts/status.sh
./scripts/stop.sh
```

日志：`logs/schedule.log`、`logs/telegram.log`

---

## 配置说明

YAML 文件在 `config/`。修改后请 `./scripts/stop.sh && ./scripts/start.sh` 重启 schedule/Telegram。`stock-helper brief` 每次运行会重新加载 YAML。

### `.env`

密钥与路径 — 见上表。运行 `stock-helper status` 查看哪些 Key 已配置。

### `config/watchlist.yaml`

```yaml
core: [AAPL, MSFT, ...]       # brief 焦点 + 新闻 ingest
lists:
  ai_infra: [...]             # 主题分组（同样 ingest）
  etfs: [SPY, QQQ, SMH]       # 早报额外报价
agent_tracking:
  enabled: true
  max_size: 15                # agent 列表上限
  auto_expire_days: 14        # 自动过期天数
```

管理 agent 列表：聊天自然语言（「关注 AMD」/ `follow NVDA`）、Telegram `/track` & `/untrack`，或 `stock-helper watchlist` 子命令。`core:` 里的核心标的需在 YAML 中修改。

### `config/alerts.yaml`

| 键 | 默认值 | 含义 |
|----|--------|------|
| `enabled` | `true` | 总开关 |
| `poll_interval_minutes` | `10` | 价格检查间隔（Finnhub `/quote`） |
| `news_ingest_every_n_polls` | `3` | 每 N 轮 poll  ingest 一次 → 默认 **30 分钟** |
| `skip_ingest_if_ran_within_minutes` | `30` | brief/CLI ingest 后跳过 alert 侧 ingest |
| `market_hours` | 07:00–20:00 ET，每天 | alert 轮询窗口（不受美股交易日限制） |
| `price.default_move_pct` | `5.0` | 默认日涨跌幅阈值（%） |
| `price.rules[]` | 如 NVDA 3%、VIX 涨 8% | 按 symbol 覆盖 |

新闻 alert 触发：SEC 表格、材料关键词、或 L1 类型（`earnings`、`m_and_a`、`legal`）。

**更灵敏：** `poll_interval_minutes: 5`，`news_ingest_every_n_polls: 2`。  
**更省 API：** `poll_interval_minutes: 15`，`news_ingest_every_n_polls: 4`。

### `config/ipos.yaml`

| 键 | 含义 |
|----|------|
| `enabled` | brief 是否显示 IPO 章节 |
| `lookahead_days` | 日历向前看天数 |
| `min_deal_value_usd` | 自动标记大额发行（如 300000000 = 3 亿美元） |
| `auto_notable` | 不在 watch 里的大额发行也展示 |
| `watch` | 始终高亮的公司名/ticker（子串匹配） |

### `config/persona.yaml`

| 键 | 含义 |
|----|------|
| `name` / `display_name` | Moka-chan 品牌名 |
| `brief_system` / `chat_system` | LLM 系统提示（`{name}` 占位） |
| `brief_greeting` | `morning` / `close` / `weekly` 开场白 |
| `chat_greeting` | Telegram `/start` 文案 |
| `chat_intro` | 简短自我介绍（不灌 brief 内容） |
| `disclaimer` | brief 页脚免责声明 |

聊天语言匹配与语气规则在 `chat_system` 中。

### `config/models.yaml`

| 区块 | 含义 |
|------|------|
| `tiers.l1/l2/l3` | 模型、temperature、max tokens |
| `node_models` | 各 Agent 节点用哪一档（聊天为 `chat_simple` / `chat_analytical` / `chat_deep`） |
| `node_overrides` | 按节点覆盖 `max_tokens` 等（如聊天回复） |
| `budget.*` | 单次 brief、聊天会话（`chat_session_max_usd`）、月度 USD 上限 |

### `config/analysis.yaml`

长期分析调度与数据范围。

| 键 | 含义 |
|----|------|
| `monthly_report` | 每月第一个交易日，默认美东 08:00 |
| `biweekly_update` | 每月 1 日、15 日及之后首个交易日，默认美东 08:15 |
| `default_risk_level` | L1 / L2 / L3 组合模板 |
| `data_refresh.fundamentals_max_age_days` | Finnhub 基本面缓存天数 |

### `config/reasoning.yaml`

Market Reasoning Agent 规则与 Reader View 输出语言。

| 键 | 含义 |
|----|------|
| `reader_report.languages` | `[zh, en]` 双语（中文在前）、`[zh]` 仅中文、`[en]` 仅英文 |
| `thesis.use_llm` | `false` = 证据推导 thesis（默认）；`true` = 可选 LLM thesis |
| `drivers.*` / `hypotheses.*` | 驱动权重与假设先验 |

### `config/strategy.yaml`

CIO 策略层——资产配置模板、行业/风格倾斜、仓位规则、风险姿态。

| 键 | 含义 |
|----|------|
| `regime_templates` | 各宏观阶段的基础资产权重 |
| `risk_level_tilt` | L1/L2/L3 股票仓位乘数 |
| `cio_report.languages` | `[zh, en]` CIO 章节双语 |
| `position_sizing` | 核心 ETF、卫星标的上限、透镜分数门槛 |

---

## 定时任务（美东 ET，`BRIEF_TIMEZONE`）

| 时间 | 任务 |
|------|------|
| 7:00 | 早报 + ingest — **仅美股交易日** |
| 16:45 | 收盘 brief + ingest — **仅美股交易日** |
| 周五 17:30 | 周报 — **仅美股交易日**（周五若是节假日则跳过） |
| 每月第一个交易日 08:00 | 月度市场与策略报告 — **仅美股交易日** |
| 每月 1 日、15 日及之后首个交易日 08:15 | 双周市场脉搏 — **仅美股交易日**（与月度同日则只跑月度） |
| 每 `poll_interval_minutes` 分钟，每天 07:00–20:00 | 价格 alert；周期性新闻 ingest |

交易日判断使用 Finnhub `/stock/market-holiday`（缓存 24 小时）。无 `FINNHUB_API_KEY` 时仅跳过周末。

brief 运行时会 ingest 一次；之后 `skip_ingest_if_ran_within_minutes` 内 alert 不再重复 ingest（避免 7:00 / 16:45 双倍拉取）。

---

## 免责声明

仅供信息参考，不构成投资建议。
