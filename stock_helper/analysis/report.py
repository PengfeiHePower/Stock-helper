from __future__ import annotations

import json
from datetime import date
from typing import Any

from stock_helper.agents.cost_tracker import get_active_tracker, reset_tracker
from stock_helper.agents.llm import LLMNotConfigured, invoke_node_llm
from stock_helper.agents.persona import brief_system_prompt, persona_disclaimer, persona_name
from stock_helper.analysis.factors import build_sector_rotation, score_universe
from stock_helper.analysis.index_explainer import explain_index_behavior, format_index_explanations_markdown
from stock_helper.analysis.formatting import fmt_num, note
from stock_helper.analysis.institutions import format_institutions_markdown, institution_filing_status
from stock_helper.analysis.regime import classify_regime, save_regime_snapshot
from stock_helper.analysis.risk_levels import format_risk_levels_markdown
from stock_helper.analysis.sentiment_layer import analyze_sentiment_layer, format_sentiment_markdown
from stock_helper.analysis.strategies import lens_consensus, persist_scores, score_watchlist_lenses
from stock_helper.analysis.structure import build_market_structure
from stock_helper.analysis.synthesis import build_beginner_storyline
from stock_helper.config import has_llm_keys, load_yaml
from stock_helper.reasoning.build import build_market_reasoning
from stock_helper.reasoning.analyst_appendix import format_analyst_appendix
from stock_helper.reasoning.reader_report import format_reader_markdown
from stock_helper.reasoning.snapshot import save_reasoning_snapshot
from stock_helper.strategy.build import build_cio_strategy
from stock_helper.strategy.cio_report import format_cio_markdown
from stock_helper.strategy.snapshot import save_strategy_snapshot
from stock_helper.storage.db import MonthlyReportRecord, get_session
from stock_helper.watchlist import all_watchlist_tickers, get_core_tickers


def _report_month(d: date | None = None) -> str:
    d = d or date.today()
    return d.strftime("%Y-%m")


def build_phase1_snapshot(refresh: bool = False, sentiment_days: int = 14) -> dict[str, Any]:
    regime_result = classify_regime()
    save_regime_snapshot(regime_result)
    structure = build_market_structure(refresh=refresh)
    index_explanations = explain_index_behavior(regime_result, structure)
    sentiment = analyze_sentiment_layer(days=sentiment_days)

    tickers = sorted(set(get_core_tickers()) | set(all_watchlist_tickers()))
    factor_rows = score_universe(tickers, refresh=refresh)
    lens_map = score_watchlist_lenses(tickers, refresh=False)
    persist_scores(factor_rows, lens_map)

    snapshot = {
        "report_month": _report_month(),
        "regime": regime_result,
        "structure": structure,
        "index_explanations": index_explanations,
        "sentiment": sentiment,
        "sectors": structure.get("sector_leaders", []) + structure.get("sector_laggards", []),
        "factor_rows": factor_rows,
        "lens_map": lens_map,
        "consensus": lens_consensus(lens_map),
        "institutions": institution_filing_status(),
    }
    reasoning = build_market_reasoning(snapshot, refresh=refresh)
    snapshot["reasoning"] = reasoning
    save_reasoning_snapshot(reasoning)
    strategy = build_cio_strategy(snapshot, refresh=refresh)
    snapshot["strategy"] = strategy
    save_strategy_snapshot(strategy)
    return snapshot


def build_monthly_snapshot(refresh: bool = False) -> dict[str, Any]:
    return build_phase1_snapshot(refresh=refresh, sentiment_days=30)


def _llm_narrative(snapshot: dict[str, Any], *, brief: bool = False) -> str:
    if not has_llm_keys(l2=True):
        return "LLM narrative skipped — structured sections above are complete."

    reset_tracker()
    tracker = get_active_tracker()
    system = brief_system_prompt()
    max_words = "350" if brief else "600"
    user = (
        "Write a beginner-friendly US market narrative.\n"
        "Use ONLY JSON facts — do not invent numbers.\n"
        "Explain macro (4 dimensions), why SPY/QQQ/DIA behave as described, "
        "breadth (RSP vs SPY), and news mood.\n"
        f"Max {max_words} words. Moka-chan tone. Not investment advice.\n\n"
        f"FACTS:\n{json.dumps(snapshot, indent=2, default=str)[:14000]}"
    )
    try:
        return invoke_node_llm("monthly_analysis", system, user, tracker)
    except LLMNotConfigured:
        return "LLM narrative unavailable."


def assemble_monthly_markdown(snapshot: dict[str, Any], narrative: str) -> str:
    regime = snapshot["regime"]
    dims = regime.get("dimension_labels") or {}
    ind = regime.get("indicators") or {}
    structure = snapshot.get("structure") or {}

    sections = [
        f"# {persona_name()} · Monthly Market & Strategy Report",
        f"**Month:** {snapshot.get('report_month')} · **Composite:** "
        f"{regime.get('regime', '—').replace('_', ' ')} "
        f"(confidence {regime.get('confidence', '—')})",
        "",
        format_reader_markdown(
            snapshot.get("reasoning") or {}, snapshot, biweekly=False, lang=_reader_lang_mode()
        ),
        "",
        "---",
        "",
        format_cio_markdown(snapshot.get("strategy") or {}),
        "",
        "---",
        "",
        format_analyst_appendix(_reasoning_for_appendix(snapshot)),
        "",
        "## Macro — Four Dimensions",
        f"| Dimension | Reading |",
        f"|-----------|---------|",
        f"| Inflation | **{dims.get('inflation', '—')}** (CPI YoY {ind.get('cpi_yoy_pct', '—')}%) |",
        f"| Growth | **{dims.get('growth', '—')}** |",
        f"| Policy | **{dims.get('policy', '—')}** (Fed {ind.get('fed_funds', '—')}%, 10Y-2Y {ind.get('yield_curve_spread', '—')}) |",
        f"| Risk | **{dims.get('risk', '—')}** (VIX {ind.get('vix', '—')}, HY spread {ind.get('hy_spread', '—')}) |",
        "",
        "**Other macro:** "
        f"PPI YoY {ind.get('ppi_yoy_pct', '—')}% · "
        f"Dollar {ind.get('dollar_index', '—')} · "
        f"WTI {ind.get('wti_oil', '—')}",
        "",
        "## Market Structure",
        f"**Breadth proxy (RSP vs SPY daily):** {structure.get('breadth', {}).get('daily_spread_pct', '—')}% — "
        f"{note(structure.get('breadth', {}).get('interpretation', ''))}",
        "",
        f"**Growth vs broad (QQQ vs SPY daily):** "
        f"{structure.get('growth_vs_broad', {}).get('daily_spread_pct', '—')}%",
        "",
        "**Sector leaders:**",
        _format_sectors(structure.get("sector_leaders") or []),
        "",
        "**Mag7 leadership (day / 52w momentum):**",
        _format_mag7(structure.get("mag7_leadership") or []),
        "",
        format_index_explanations_markdown(snapshot.get("index_explanations") or []),
        "",
        "## Sentiment (news)",
        format_sentiment_markdown(snapshot.get("sentiment") or {}),
        "",
        format_risk_levels_markdown(regime.get("regime", "recovery")),
        "",
        "## Watchlist Factor Scores",
        _format_factors_table(snapshot.get("factor_rows") or []),
        "",
        "## Strategy Lens Fit",
        _format_lens_summary(snapshot.get("lens_map") or {}),
        "",
        "### Consensus (2+ lenses ≥ 65)",
        _format_consensus(snapshot.get("consensus") or {}),
        "",
        format_institutions_markdown(snapshot.get("institutions") or []),
        "",
        "## Narrative",
        narrative if narrative else "_Monthly narrative available in deep dive; reader summary above._",
        "",
        persona_disclaimer(),
    ]
    return "\n".join(sections)


def _reasoning_for_appendix(snapshot: dict[str, Any]) -> dict[str, Any]:
    reasoning = dict(snapshot.get("reasoning") or {})
    sentiment = snapshot.get("sentiment") or {}
    lines = []
    for v in sentiment.get("voices") or []:
        for h in v.get("sample_headlines") or []:
            lines.append(f"- {h[:140]}")
    if lines:
        reasoning["_sentiment_headlines"] = "\n".join(lines[:12])
    return reasoning


def _reader_lang_mode() -> str:
    langs = (load_yaml("reasoning.yaml").get("reader_report") or {}).get("languages") or ["zh", "en"]
    if len(langs) >= 2 or "both" in langs:
        return "both"
    return langs[0] if langs else "en"


def assemble_biweekly_markdown(snapshot: dict[str, Any], narrative: str) -> str:
    lang = _reader_lang_mode()
    return "\n".join(
        [
            f"# {persona_name()} · Biweekly Market Pulse / 双周市场脉搏",
            f"**Date / 日期:** {date.today().isoformat()}",
            "",
            format_reader_markdown(
                snapshot.get("reasoning") or {}, snapshot, biweekly=True, lang=lang
            ),
            "",
            "---",
            "",
            format_cio_markdown(snapshot.get("strategy") or {}),
            "",
            "---",
            "",
            format_analyst_appendix(_reasoning_for_appendix(snapshot)),
            "",
            persona_disclaimer(),
        ]
    )


def _format_mag7(rows: list[dict]) -> str:
    if not rows:
        return "Mag7 data unavailable."
    return "\n".join(
        f"- **{r['ticker']}** day {fmt_num(r.get('day_change_pct'), 2)}% · "
        f"momentum {fmt_num(r.get('momentum_52w'), 1)}"
        for r in rows
    )


def _format_factors_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Ticker | Quality | Value | Momentum | Low Risk | Composite |",
        "|--------|---------|-------|----------|----------|-----------|",
    ]
    for row in rows:
        f = row.get("factors") or {}
        lines.append(
            f"| {row.get('ticker')} | {f.get('quality', '—')} | {f.get('value', '—')} | "
            f"{f.get('momentum', '—')} | {f.get('low_risk', '—')} | {row.get('composite', '—')} |"
        )
    return "\n".join(lines)


def _format_lens_summary(lens_map: dict[str, list[dict[str, Any]]]) -> str:
    lines = []
    for ticker, lenses in sorted(lens_map.items()):
        if lenses:
            lines.append(f"- **{ticker}** — `{lenses[0]['lens_id']}` ({lenses[0]['score']})")
    return "\n".join(lines) if lines else "No lens scores."


def _format_sectors(sectors: list[dict[str, Any]]) -> str:
    lines = []
    for row in sectors[:6]:
        lines.append(
            f"- **{row.get('etf')}** momentum {row.get('momentum_score', '—')} "
            f"(vs SPY {row.get('vs_spy', '—')})"
        )
    return "\n".join(lines) if lines else "Sector data unavailable."


def _format_consensus(consensus: dict[str, Any]) -> str:
    hits = consensus.get("consensus") or {}
    if not hits:
        return "No multi-lens consensus."
    lines = [f"- **{t}**: {', '.join(l)}" for t, l in hits.items()]
    return "\n".join(lines)


def save_monthly_report(markdown: str, snapshot: dict[str, Any]) -> None:
    session = get_session()
    session.add(
        MonthlyReportRecord(
            report_month=snapshot.get("report_month", _report_month()),
            markdown=markdown,
            snapshot_json=json.dumps(snapshot, default=str),
            regime=(snapshot.get("regime") or {}).get("regime"),
        )
    )
    session.commit()
    session.close()


def get_latest_monthly_report() -> dict[str, Any] | None:
    session = get_session()
    row = session.query(MonthlyReportRecord).order_by(MonthlyReportRecord.id.desc()).first()
    session.close()
    if not row:
        return None
    return {
        "report_month": row.report_month,
        "markdown": row.markdown,
        "snapshot": json.loads(row.snapshot_json or "{}"),
        "regime": row.regime,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def run_monthly_report(refresh: bool = False) -> str:
    snapshot = build_monthly_snapshot(refresh=refresh)
    _ = _llm_narrative(snapshot, brief=False)  # optional cache; reader view is rule-based
    markdown = assemble_monthly_markdown(snapshot, "")
    save_monthly_report(markdown, snapshot)
    return markdown


def run_biweekly_pulse(refresh: bool = False) -> str:
    snapshot = build_phase1_snapshot(refresh=refresh, sentiment_days=14)
    return assemble_biweekly_markdown(snapshot, "")
