from __future__ import annotations

import re

from datetime import date
from typing import Any

from stock_helper.analysis.formatting import note
from stock_helper.analysis.factors import score_ticker_factors
from stock_helper.analysis.regime import classify_regime, get_latest_regime
from stock_helper.analysis.report import get_latest_monthly_report, run_monthly_report
from stock_helper.analysis.risk_levels import allocation_for_regime, default_risk_level
from stock_helper.analysis.strategies import score_strategy_lenses
from stock_helper.collectors.fundamentals import load_fundamentals_map
from stock_helper.validators import is_valid_ticker

_TICKER_RE = re.compile(r"(?<![A-Z])([A-Z]{2,5})(?![A-Z])")

_REGIME_PHRASES = (
    "长期市场",
    "长期大盘",
    "市场分析",
    "market regime",
    "long-term market",
    "macro outlook",
    "月度报告",
    "monthly report",
)

_STOCK_PHRASES = (
    "长期分析",
    "长期投资",
    "策略分析",
    "分析一下",
    "怎么看",
    "long-term",
    "strategy view",
    "factor score",
)

_LEVEL_RE = re.compile(r"\bL[123]\b|保守|均衡|进取|conservative|balanced|aggressive", re.I)

_STRATEGY_PHRASES = (
    "投资策略",
    "资产配置",
    "组合建议",
    "cio",
    "allocation",
    "portfolio template",
    "策略推荐",
    "仓位建议",
    "strategy recommendation",
)


def _is_strategy_query(message: str) -> bool:
    lower = message.lower()
    return any(p in lower or p in message for p in _STRATEGY_PHRASES)


def extract_tickers(message: str) -> list[str]:
    upper = message.upper()
    seen: set[str] = set()
    out: list[str] = []
    for match in _TICKER_RE.finditer(upper):
        t = match.group(1)
        if t in seen or not is_valid_ticker(t):
            continue
        seen.add(t)
        out.append(t)
    return out


def _parse_risk_level(message: str) -> str:
    lower = message.lower()
    if "保守" in message or "conservative" in lower or "l1" in lower:
        return "L1"
    if "进取" in message or "aggressive" in lower or "l3" in lower:
        return "L3"
    if "均衡" in message or "balanced" in lower or "l2" in lower:
        return "L2"
    return default_risk_level()


def _is_regime_query(message: str) -> bool:
    lower = message.lower()
    return any(p in lower or p in message for p in _REGIME_PHRASES)


def _is_stock_analysis_query(message: str) -> bool:
    lower = message.lower()
    if _is_regime_query(message):
        return False
    if any(p in lower or p in message for p in _STOCK_PHRASES):
        return True
    tickers = extract_tickers(message)
    return bool(tickers) and any(
        w in lower for w in ("分析", "看", "strategy", "lens", "factor", "长期")
    )


def handle_analysis_chat(message: str, lang: str = "en") -> str | None:
    lower = message.lower().strip()
    if "刷新" in message or "refresh" in lower:
        if any(p in lower for p in ("月度", "monthly", "报告", "report")):
            return run_monthly_report(refresh=True)[:3500]

    if _is_strategy_query(message):
        return _strategy_reply(message, lang)

    if _is_regime_query(message):
        return _regime_reply(lang)

    if any(p in message.lower() for p in ("结构", "breadth", "rsp", "广度", "板块轮动", "市场结构")):
        return _reasoning_reply(lang, compact=True)

    if any(
        p in message.lower()
        for p in ("thesis", "叙事", "发生了什么", "市场故事", "top driver", "驱动", "冲突")
    ):
        return _reasoning_reply(lang, compact=False)

    if _is_stock_analysis_query(message):
        return _stock_reply(message, lang)

    if any(p in lower for p in ("策略分歧", "consensus", "共识", "lens")):
        return _consensus_reply(lang)

    if any(p in lower for p in ("机构", "13f", "institution", "berkshire", "ark")):
        from stock_helper.analysis.institutions import format_institutions_markdown, institution_filing_status

        return format_institutions_markdown(institution_filing_status())

    return None


def _reply(lang: str, zh: str, en: str) -> str:
    return zh if lang == "zh" else en


def _fmt(val) -> str:
    if val is None:
        return "—"
    if isinstance(val, float):
        return str(round(val, 1))
    return str(val)


def _reasoning_reply(lang: str, *, compact: bool) -> str:
    from stock_helper.analysis.report import build_phase1_snapshot
    from stock_helper.reasoning.reader_report import format_reader_markdown
    from stock_helper.reasoning.snapshot import get_latest_reasoning_snapshot

    today = date.today().isoformat()
    latest = get_latest_reasoning_snapshot()
    snapshot: dict[str, Any] | None = None
    if latest and (latest.get("as_of_date") == today or latest.get("_meta", {}).get("as_of_date") == today):
        reasoning = latest
        snap = build_phase1_snapshot(refresh=False)
        snapshot = snap
    else:
        snap = build_phase1_snapshot(refresh=False)
        reasoning = snap.get("reasoning") or {}
        snapshot = snap

    use_lang = "zh" if lang == "zh" else "en"
    body = format_reader_markdown(reasoning, snapshot, biweekly=True, lang=use_lang)
    if lang == "zh":
        return f"📊 **市场速览**\n\n{body[:3500]}"
    return f"📊 **Market pulse**\n\n{body[:3500]}"


def _strategy_reply(message: str, lang: str) -> str:
    from stock_helper.analysis.report import build_phase1_snapshot
    from stock_helper.strategy.cio_report import format_cio_markdown
    from stock_helper.strategy.snapshot import get_latest_strategy_snapshot

    level = _parse_risk_level(message)
    today = date.today().isoformat()
    latest = get_latest_strategy_snapshot()
    if latest and (latest.get("as_of_date") == today or latest.get("_meta", {}).get("as_of_date") == today):
        if latest.get("risk_level") == level:
            strategy = latest
        else:
            snap = build_phase1_snapshot(refresh=False)
            from stock_helper.strategy.build import build_cio_strategy

            strategy = build_cio_strategy(snap, risk_level=level, refresh=False)
    else:
        snap = build_phase1_snapshot(refresh=False)
        from stock_helper.strategy.build import build_cio_strategy

        strategy = build_cio_strategy(snap, risk_level=level, refresh=False)

    use_lang = "zh" if lang == "zh" else "en"
    body = format_cio_markdown(strategy, lang=use_lang)
    if lang == "zh":
        return f"📋 **CIO 策略建议**（{level}）\n\n{body[:3500]}"
    return f"📋 **CIO Strategy** ({level})\n\n{body[:3500]}"


def _regime_reply(lang: str) -> str:
    from stock_helper.reasoning.snapshot import get_latest_reasoning_snapshot

    latest_reasoning = get_latest_reasoning_snapshot()
    thesis_line = ""
    if latest_reasoning:
        thesis_line = (latest_reasoning.get("thesis") or {}).get("headline", "")

    latest = get_latest_monthly_report()
    regime = None
    if latest:
        regime = latest.get("snapshot", {}).get("regime")
    if not regime:
        regime = classify_regime()

    dims = regime.get("dimension_labels") or {}
    if not dims and regime.get("dimensions"):
        dims = {k: v.get("label") for k, v in regime["dimensions"].items()}
    ind = regime.get("indicators") or {}
    level = default_risk_level()
    alloc = allocation_for_regime(regime.get("regime", "recovery"), level)

    if lang == "zh":
        lines = [
            f"📊 **长期市场（四维宏观）**",
            f"综合：**{regime.get('regime', '—').replace('_', ' ')}** · "
            f"通胀 {dims.get('inflation', '—')} · 增长 {dims.get('growth', '—')} · "
            f"政策 {dims.get('policy', '—')} · 风险 {dims.get('risk', '—')}",
            f"CPI YoY {ind.get('cpi_yoy_pct', '—')}% · VIX {ind.get('vix', '—')} · "
            f"10Y-2Y {ind.get('yield_curve_spread', '—')}",
            f"默认 **{level} {alloc.get('label_zh')}**：股票约 {alloc['equity_budget_pct']}%",
            note(alloc.get("regime_note", "")),
        ]
        if thesis_line:
            lines.insert(1, f"**今日论点：** {thesis_line}")
        return "\n".join(lines)
    lines = [
        f"📊 **Long-term market (4 macro dimensions)**",
        f"Composite: **{regime.get('regime', '—')}** · "
        f"inflation {dims.get('inflation')} · growth {dims.get('growth')} · "
        f"policy {dims.get('policy')} · risk {dims.get('risk')}",
        f"CPI YoY {ind.get('cpi_yoy_pct')}% · VIX {ind.get('vix')} · "
        f"curve {ind.get('yield_curve_spread')}",
        f"Default **{level}**: ~{alloc['equity_budget_pct']}% equity",
        note(alloc.get("regime_note", "")),
    ]
    if thesis_line:
        lines.insert(1, f"**Today's thesis:** {thesis_line}")
    return "\n".join(lines)


def _stock_reply(message: str, lang: str) -> str:
    tickers = extract_tickers(message)
    if not tickers:
        return _reply(
            lang,
            "想长期分析哪只？例如：「长期分析一下 NVDA」或「L3 看 AMD」",
            "Which ticker? e.g. long-term view on NVDA, or L3 view on AMD",
        )

    level = _parse_risk_level(message)
    funds = load_fundamentals_map(tickers, refresh=False)
    lines: list[str] = []

    regime = get_latest_regime() or classify_regime()
    alloc = allocation_for_regime(regime.get("regime", "recovery"), level)

    header_zh = f"📈 长期个股分析 · 档位 {level}（{alloc.get('label_zh')}）"
    header_en = f"📈 Long-term stock view · level {level} ({alloc.get('label')})"
    lines.append(header_zh if lang == "zh" else header_en)

    for ticker in tickers:
        data = funds.get(ticker.upper())
        if not data:
            lines.append(f"- {ticker}: no fundamentals cached")
            continue
        factors = score_ticker_factors(data)
        lenses = score_strategy_lenses(ticker, data)
        f = factors.get("factors") or {}
        best = lenses[0] if lenses else None
        lines.append(
            f"**{ticker}** composite {factors.get('composite')} · "
            f"Q{_fmt(f.get('quality'))} V{_fmt(f.get('value'))} "
            f"M{_fmt(f.get('momentum'))} R{_fmt(f.get('low_risk'))}"
        )
        if best:
            lines.append(
                f"  best lens: {best['lens_id']} ({best['score']}) — {best.get('name')}"
            )

    lines.append(
        _reply(
            lang,
            f"档位 {level} 建议股票仓位约 {alloc['equity_budget_pct']}%，单票上限 {alloc['max_single_stock_pct']}%。",
            f"Level {level}: ~{alloc['equity_budget_pct']}% equity, max {alloc['max_single_stock_pct']}% per name.",
        )
    )
    return "\n".join(lines)


def _consensus_reply(lang: str) -> str:
    latest = get_latest_monthly_report()
    if not latest:
        return _reply(
            lang,
            "还没有月度报告缓存，可以说「刷新月度报告」先生成。",
            "No monthly cache yet — ask to refresh the monthly report first.",
        )
    consensus = (latest.get("snapshot") or {}).get("consensus") or {}
    hits = consensus.get("consensus") or {}
    if not hits:
        return _reply(lang, "本月暂无多策略共识标的。", "No multi-lens consensus this month.")
    lines = [_reply(lang, "**策略共识**", "**Strategy consensus**")]
    for ticker, lenses in hits.items():
        lines.append(f"- {ticker}: {', '.join(lenses)}")
    return "\n".join(lines)
