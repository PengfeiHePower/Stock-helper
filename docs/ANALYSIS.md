# Long-Term Analysis — Methods & Models

This document describes how **monthly market analysis** and **strategy lenses** work in Stock Helper. It is designed for a **6–12 month horizon**, not day-trading.

## Design principle: hybrid, not LLM-only

| Layer | What it does | Model / method |
|-------|----------------|----------------|
| **Quant / rules** | Regime, factors, lens scores | Deterministic Python — **no trained ML** |
| **Data** | Macro, fundamentals, quotes | FRED + Finnhub (cached monthly) |
| **Narrative** | Readable report & chat | **Claude Sonnet** (`monthly_analysis` node) — explains JSON only |
| **Daily brief LLM** | Unchanged | Gemini L1 + Claude L2/L3 |

The LLM **never invents** P/E, ROE, or regime labels. It only narrates structured output.

---

## 1. Market regime (macro)

**File:** `stock_helper/analysis/regime.py`

**Method:** Rule-based classifier over FRED series:

| Indicator | FRED ID | Use |
|-----------|---------|-----|
| Yield curve | `T10Y2Y` | Inversion → slowdown / recession risk |
| VIX | `VIXCLS` | Stress level |
| Unemployment trend | `UNRATE` (3m change) | Labour market direction |
| Fed funds / 10Y | `DFF`, `DGS10` | Context in dashboard |

**Output labels:** `expansion`, `slowdown`, `recession_risk`, `recovery`

This is **not** a neural network or econometric forecast model. Thresholds live in `config/analysis.yaml` → `regime:`.

---

## 2. Factor scores (stocks & ETFs)

**File:** `stock_helper/analysis/factors.py`

**Method:** Heuristic scoring (0–100) from Finnhub `/stock/metric` + `/quote`:

| Factor | Inputs | Idea |
|--------|--------|------|
| **Quality** | `roeTTM` | Higher ROE → higher score |
| **Value** | `peTTM` | Lower P/E → higher score (sector-agnostic simple rule) |
| **Momentum** | Price vs 52-week range | Proxy for 6–12m trend (Finnhub candle API not required) |
| **Low risk** | `beta` | Lower beta → higher score |

**Composite:** Average of available factors.

Sector rotation ranks sector ETFs (XLK, XLF, …) by momentum vs SPY using the same proxy.

Fundamentals are **cached** in SQLite (`fundamental_snapshots`) and refreshed monthly by default (`data_refresh.fundamentals_max_age_days`).

---

## 3. Strategy lenses (investor / institution style)

**File:** `stock_helper/analysis/strategies.py`  
**Config:** `config/strategies.yaml`

Each lens is a **weighted blend of factors** — a distilled, rule-based version of well-known approaches:

| Lens ID | Style | Typical weights |
|---------|--------|-----------------|
| `buffett_quality` | Quality + value | quality, value |
| `bogle_core_satellite` | Index core + quality satellites | quality, low_risk |
| `dalio_all_weather` | Stability / macro defensive | low_risk, quality |
| `momentum_trend` | Trend following | momentum |
| `defensive_dividend` | Defensive | quality, value, low_risk |

**Not** a fine-tuned “Buffett GPT”. The philosophy is encoded in weights + factor rules; Claude only explains results.

**Consensus:** Tickers where ≥2 lenses score ≥ 65. **Disagreements:** Large spread between best and worst lens.

---

## 4. Risk levels (L1 / L2 / L3)

**File:** `stock_helper/analysis/risk_levels.py`  
**Config:** `config/analysis.yaml` → `risk_levels`

| Level | Default | Equity budget | Max single stock |
|-------|---------|---------------|------------------|
| **L1** | Conservative | ~40% (adjusted by regime) | 5% |
| **L2** | Balanced (default) | ~65% | 8% |
| **L3** | Aggressive | ~85% | 12% |

Regime multiplies equity tilt (e.g. `recession_risk` reduces equity %). Output is **educational allocation template**, not a trade order.

---

## 5. Institution tracking

**Config:** `config/institutions.yaml`

Tracked entities (your list):

- Berkshire Hathaway  
- Vanguard  
- Bridgewater  
- BlackRock  
- ARK Invest  
- Elliott Management  

**Current capability:** SEC EDGAR submission check for latest **13F-HR** filing date per CIK.  
**Planned:** Holdings parse + quarter-over-quarter theme diff.

Each institution maps to a default `strategy_lens` for narrative alignment.

---

## 6. Market Reasoning Agent (Phase 2)

**Package:** `stock_helper/reasoning/`  
**Config:** `config/reasoning.yaml`

The reasoning layer turns Phase 1 facts into a **thesis-first** report. It answers:

1. **What is happening?** → `thesis.py` (Today's Thesis)
2. **Why?** → `causality.py`, `evidence_graph.py`, `conflict.py`
3. **What to watch?** → `change_detector.py`, `scenarios.py`, `driver_ranker.py`

| Module | Phase | Role |
|--------|-------|------|
| `signals.py` | 2a | Per-layer bullish/bearish/neutral + confidence |
| `conflict.py` | 2a | Cross-layer conflict detection |
| `change_detector.py` | 2a | Diff vs prior `ReasoningSnapshot` |
| `driver_ranker.py` | 2a | Top 3 drivers with importance weights |
| `thesis.py` | 2a | Market thesis (rules + optional LLM) |
| `breadth_deep.py` | 2b | RSP/SPY/IWM, sector day moves, Mag7 concentration |
| `causality.py` | 2b | Macro cause → effect chains |
| `evidence_graph.py` | 2b | Hierarchy: macro → rates → sector → index |
| `narrative_topics.py` | 2c | Topic → narrative → implication + shift detection |
| `counter_evidence.py` | 2c | Bull vs bear case, confidence adjustment |
| `scenarios.py` | 2c | CPI / earnings / risk-off scenario branches |

Snapshots persist in SQLite (`reasoning_snapshots`) for **What Changed**.

Chat: `市场结构`, `市场故事`, `thesis`, `发生了什么` → thesis-first reasoning reply.

**Next layer:** CIO Strategy recommendations — see [docs/STRATEGY.md](STRATEGY.md).

---

## 7. LLM usage

| Node | Tier | Model (Plan A) | Role |
|------|------|----------------|------|
| `monthly_analysis` | L2 | Claude Sonnet | Monthly narrative (appendix) |
| `market_reasoning` | L2 | Claude Sonnet | Today's thesis (constrained) |
| `chat_simple` | L1 | Gemini Flash-Lite | Light chat |
| `chat_analytical` / `chat_deep` | L2/L3 | Claude Sonnet | Daily Q&A |

Monthly report = **structured snapshot JSON** → one L2 call for narrative section.

---

## 8. Scheduling & chat

| Trigger | Behavior |
|---------|----------|
| First **US trading day** of month, 08:00 ET | Auto monthly report → email + Telegram |
| `stock-helper analyze` / `monthly` | Manual full run |
| `stock-helper analyze --refresh` | Force refresh Finnhub fundamentals |
| Chat: 长期市场 / 长期分析 NVDA / L3 看 AMD | `analysis/chat.py` reads cache + rules |

| Chat: 市场结构 / 市场故事 / thesis | Reasoning report (thesis-first) |

---

## 9. Limitations (honest)

- Momentum uses **52-week range position**, not full 12m return (Finnhub candle may be premium).  
- Value score uses simple P/E buckets, not sector-relative DCF.  
- Regime rules are US-centric and may lag turning points.  
- Flow / options positioning not yet in conflict layer (Phase 3).  
- Advance/decline and new high/low need additional data feed.  
- Historical analog table not yet curated.  
- **Not investment advice.**

---

## 10. File map

```
config/analysis.yaml      # regime thresholds, risk levels, scope
config/strategies.yaml    # lens weights
config/institutions.yaml  # 13F CIKs
stock_helper/analysis/
  macro_series.py         # FRED history
  regime.py               # rule classifier
  factors.py              # factor + sector scores
  strategies.py           # lens scoring + consensus
  risk_levels.py          # L1/L2/L3 templates
  institutions.py         # SEC 13F status
  report.py               # assemble + LLM narrative
  pipeline.py             # deliver email/Telegram
  chat.py                 # chat intents
stock_helper/reasoning/     # Phase 2 Market Reasoning Agent
  build.py                  # orchestrator
  thesis.py conflict.py     # 2a core
  causality.py breadth_deep.py evidence_graph.py  # 2b
  narrative_topics.py counter_evidence.py scenarios.py  # 2c
  report.py snapshot.py
config/reasoning.yaml
```
