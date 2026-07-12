from __future__ import annotations

from typing import Any

from stock_helper.analysis.formatting import note
from stock_helper.cio.report_zh import format_cio_pipeline_zh
from stock_helper.config import load_yaml


def _lang_mode() -> str:
    langs = (load_yaml("cio.yaml").get("report") or {}).get("languages") or ["zh", "en"]
    if len(langs) >= 2 or "both" in langs:
        return "both"
    return langs[0] if langs else "en"


def format_cio_pipeline(cio: dict[str, Any], *, lang: str | None = None) -> str:
    mode = lang or _lang_mode()
    if mode == "zh":
        return format_cio_pipeline_zh(cio)
    if mode == "both":
        return f"{format_cio_pipeline_zh(cio)}\n\n---\n\n{_format_cio_pipeline_en(cio)}"
    return _format_cio_pipeline_en(cio)


def _format_cio_pipeline_en(cio: dict[str, Any]) -> str:
    ex = cio.get("executive_summary") or {}
    regime = cio.get("regime") or {}
    themes = cio.get("theme_rotation") or {}
    industries = cio.get("industry_rotation") or {}
    stocks = cio.get("stock_ranking") or {}
    portfolio = cio.get("portfolio") or {}
    scenarios = cio.get("scenarios") or {}
    triggers = cio.get("triggers") or {}
    monitor = cio.get("monitoring") or {}

    lines = [
        "# CIO Investment Outlook",
        f"**Date:** {cio.get('as_of_date')} · **Risk profile:** {cio.get('risk_level', 'L2')}",
        "",
        "## Executive Summary",
        "",
        ex.get("text_en", ""),
        "",
        "---",
        "",
        "## 1. Market Regime",
        "",
        f"**Current regime:** {regime.get('current_regime')}",
        f"**Confidence:** {regime.get('confidence_label', '—')} ({_fmt(regime.get('confidence'))})",
        "",
        "### Market Narrative",
        "",
        regime.get("market_narrative", ""),
        "",
        "**Key drivers:** " + " · ".join(regime.get("key_drivers") or []),
        "",
        "### Key Conflict",
        "",
    ]
    for step in (regime.get("key_conflict") or {}).get("chain") or []:
        lines.append(f"- {step}")
    lines.append(f"\n**Overall:** {(regime.get('key_conflict') or {}).get('overall', '')}")
    lines.extend(["", "---", "", "## 2. Theme Rotation", "", "### Winning Themes", ""])

    for t in (themes.get("winning_themes") or [])[:6]:
        lines.append(f"**{t.get('name')}** {t.get('rating')}")
        lines.append(
            f"- Momentum: {t.get('momentum')} · Macro: {t.get('macro_support')} · "
            f"Valuation: {t.get('valuation')} · Decision: **{t.get('decision')}**"
        )
        r = t.get("reasoning") or {}
        if r.get("hypothesis"):
            lines.append(f"- Hypothesis: {r['hypothesis']}")
        tid = t.get("id")
        sub_inds = (industries.get("by_theme") or {}).get(tid) or []
        if sub_inds:
            lines.append("- Industries: " + ", ".join(
                f"{i.get('name')} {i.get('rating')}" for i in sub_inds[:5]
            ))
        lines.append("")

    lines.append("### Weak Themes")
    for w in themes.get("weak_themes") or []:
        lines.append(f"- {w.get('name')} — {w.get('reason')}")

    lines.extend(["", "---", "", "## 3. Industry Rotation", ""])
    for ind in (industries.get("top_industries") or [])[:8]:
        lines.append(f"### {ind.get('name')} {ind.get('rating')}")
        lines.append(
            f"Trend: {ind.get('trend')} · Catalyst: {ind.get('catalyst')} · "
            f"Valuation: {ind.get('valuation')} · Risk: {ind.get('risk')}"
        )
        reps = ", ".join(ind.get("representative_stocks") or [])
        if reps:
            lines.append(f"Representative: {reps}")
        lines.append("")

    lines.extend(["---", "", "## 4. Stock Ranking", ""])
    by_ind = stocks.get("by_industry") or {}
    shown = 0
    for iname, lst in by_ind.items():
        if shown >= 4:
            break
        lines.append(f"### {iname}")
        for s in lst[:2]:
            lines.append(
                f"**{s['ticker']}** {s.get('rating')} — "
                f"{'; '.join(s.get('why') or [])} · Valuation: {s.get('valuation')} · "
                f"Confidence: {s.get('confidence')}"
            )
        lines.append("")
        shown += 1

    lines.extend(["---", "", "## 5. Portfolio Construction", "", "### Strategic Allocation (US only)", ""])
    lines.append("| Asset | Weight | Proxy |")
    lines.append("|-------|--------|-------|")
    for row in portfolio.get("strategic_allocation") or []:
        lines.append(f"| {row.get('label')} | {row.get('weight_pct')}% | {row.get('proxy') or '—'} |")

    lines.extend(["", "### Active Tilts", ""])
    for t in portfolio.get("active_tilts") or []:
        lines.append(f"- {t.get('direction')}{t.get('tilt_pct')}% {t.get('target')}")

    lines.append("")
    lines.append("**ETF implementation:** " + ", ".join(portfolio.get("etf_implementation") or []))
    if portfolio.get("stock_sleeve"):
        lines.append("")
        lines.append("**Stock sleeve:** " + ", ".join(
            f"{s['ticker']} ({s['weight_pct']}%)" for s in portfolio["stock_sleeve"]
        ))

    lines.extend(["", "---", "", "## 6. Scenario Planning", ""])
    for sc in scenarios.get("scenarios") or []:
        lines.append(f"**{sc.get('name')}** ({sc.get('probability_pct')}%) — {sc.get('narrative')}")
        lines.append(f"- Action: {sc.get('portfolio_action')}")
        lines.append("")

    lines.extend(["---", "", "## 7. Trigger Engine", ""])
    for tr in triggers.get("triggers") or []:
        flag = "**[ACTIVE]** " if tr.get("active") else ""
        lines.append(f"{flag}**If** {tr.get('if')}")
        for step in tr.get("then") or []:
            lines.append(f"  → {step}")
        lines.append("")

    lines.extend(["---", "", "## 8. Monitoring Dashboard", "", "### Market Health", ""])
    for dim, data in (monitor.get("market_health") or {}).items():
        if isinstance(data, dict):
            lines.append(f"- **{dim.title()}** {data.get('rating')} ({data.get('score')})")

    lines.extend(["", "### Watch List", ""])
    earnings = monitor.get("earnings_calendar") or []
    if earnings:
        lines.append("**Earnings calendar (Finnhub):**")
        for w in earnings:
            imp = w.get("importance", "").replace("_", " ").title()
            theme = w.get("theme") or ""
            ind = w.get("industry") or ""
            ctx = f" · {theme} / {ind}" if theme else ""
            lines.append(
                f"- **{w.get('ticker')}** {w.get('date')} ({w.get('hour')}) — "
                f"{w.get('timing')} · {imp}{ctx}"
            )
        lines.append("")
    for w in monitor.get("macro_watch") or monitor.get("watch_list") or []:
        if w.get("source") == "finnhub_earnings":
            continue
        imp = w.get("importance", "").replace("_", " ").title()
        lines.append(f"- **{w.get('event')}** — {w.get('timing')} · {imp}")

    lines.extend(["", note(cio.get("disclaimer", ""))])
    return "\n".join(lines)


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)
