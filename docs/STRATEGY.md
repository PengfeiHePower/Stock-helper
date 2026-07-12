# CIO Investment Agent — Investment Decision Pipeline

> An investment reasoning system that progressively transforms macro evidence into actionable portfolio decisions through hierarchical reasoning: **Market → Theme → Industry → Company → Portfolio**.

**US equities only.** Not personalized investment advice.

---

## Architecture

```
                 CIO Investment Agent
                         │
 ───────────────────────────────────────────────
        1. Market Regime Analysis
 ───────────────────────────────────────────────
                         │
                 Evidence Fusion (Analysis + Reasoning)
                         │
               Market Narrative
                         │
 ───────────────────────────────────────────────
        2. Theme Rotation Engine
 ───────────────────────────────────────────────
                         │
                Theme Ranking ★★★★★
                         │
 ───────────────────────────────────────────────
        3. Industry Rotation Engine
 ───────────────────────────────────────────────
                         │
              Industry Ranking
                         │
 ───────────────────────────────────────────────
        4. Stock Selection Engine
 ───────────────────────────────────────────────
                         │
               Company Ranking
                         │
 ───────────────────────────────────────────────
        5. Portfolio Construction
 ───────────────────────────────────────────────
                         │
               Risk Management
                         │
        6. Scenario Planning
        7. Trigger Engine (If → Then)
        8. Monitoring Dashboard
```

**Cross-cutting:** `cio/reasoning_chain.py` — Evidence → Hypothesis → Counter Evidence → Confidence → Decision (applied to Theme, Industry, Stock, Portfolio).

---

## Package layout

| Layer | Module |
|-------|--------|
| Orchestrator | `cio/pipeline.py` → `build_cio_pipeline()` |
| 1 Regime | `cio/regime.py` |
| 2 Theme | `cio/themes.py` |
| 3 Industry | `cio/industries.py` |
| 4 Stock | `cio/stocks.py` |
| 5 Portfolio | `cio/portfolio.py` |
| 6 Scenario | `cio/scenarios.py` |
| 7 Triggers | `cio/triggers.py` |
| 8 Monitor | `cio/monitoring.py` |
| Report | `cio/report.py`, `cio/report_zh.py` |

Config: **`config/cio.yaml`** (themes, industries, US allocation, triggers, watch keywords).

Consumes: `build_phase1_snapshot()` outputs — `regime`, `structure`, `sentiment`, `reasoning`, `factor_rows`, `lens_map`, `consensus`.

Persists: `strategy_snapshots` table (JSON v2).

---

## Final report order

1. Executive Summary  
2. Market Regime + Narrative + Conflict  
3. Theme Rotation (winning / weak)  
4. Industry Rotation (per theme)  
5. Stock Ranking (by industry)  
6. Portfolio (strategic + tilts + ETF + stock sleeve)  
7. Scenario Planning (base / bull / bear)  
8. Trigger Engine (If → Then)  
9. Monitoring Dashboard + Watch List  

---

## Commands

```bash
stock-helper strategy
stock-helper strategy --level L1
stock-helper biweekly    # Reader View + full CIO outlook + appendix
```

Chat: `投资策略` / `资产配置` / `CIO`

---

## Phase 2 enhancements (implemented)

- **Expanded theme/industry tree** in `config/cio.yaml` (AI → GPU/Memory/…, Defense → Missile/Radar/…, Consumer sub-sectors)
- **Finnhub earnings calendar** in Watch List via `cio/earnings_watch.py` + `config/cio_earnings.yaml`

## Phase 2+ (research roadmap)

- Portfolio Construction with **user holdings**
- Rebalancing drift engine
- Tax-loss harvesting agent
- LLM narrative polish per layer (evidence-constrained)
- Theme/industry config curation + 13F theme validation
