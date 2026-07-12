from __future__ import annotations

from typing import Any

from stock_helper.analysis.formatting import note


def format_cio_pipeline_zh(cio: dict[str, Any]) -> str:
    ex = cio.get("executive_summary") or {}
    regime = cio.get("regime") or {}
    themes = cio.get("theme_rotation") or {}
    industries = cio.get("industry_rotation") or {}
    stocks = cio.get("stock_ranking") or {}
    portfolio = cio.get("portfolio") or {}
    scenarios = cio.get("scenarios") or {}
    triggers = cio.get("triggers") or {}
    monitor = cio.get("monitoring") or {}

    conf_zh = {"High": "高", "Moderate": "中等", "Low": "低"}.get(
        regime.get("confidence_label", ""), regime.get("confidence_label", "—")
    )

    lines = [
        "# CIO 投资展望",
        f"**日期：** {cio.get('as_of_date')} · **风险档位：** {cio.get('risk_level', 'L2')}",
        "",
        "## 执行摘要",
        "",
        ex.get("text_zh", ""),
        "",
        "---",
        "",
        "## 1. 市场阶段（Regime）",
        "",
        f"**当前阶段：** {regime.get('current_regime_zh') or regime.get('current_regime')}",
        f"**把握度：** {conf_zh}（{_fmt(regime.get('confidence'))}）",
        "",
        "### 市场叙事",
        "",
        regime.get("market_narrative_zh") or regime.get("market_narrative", ""),
        "",
        "**关键驱动：** " + " · ".join(regime.get("key_drivers") or []),
        "",
        "### 核心矛盾",
        "",
    ]
    for step in (regime.get("key_conflict") or {}).get("chain") or []:
        lines.append(f"- {step}")
    lines.append(f"\n**综合判断：** {(regime.get('key_conflict') or {}).get('overall', '')}")

    lines.extend(["", "---", "", "## 2. 主题轮动（Theme）", "", "### 强势主题", ""])
    for t in (themes.get("winning_themes") or [])[:6]:
        lines.append(f"**{t.get('name_zh') or t.get('name')}** {t.get('rating')}")
        dec = {"Overweight": "超配", "Neutral": "中性", "Underweight": "低配"}.get(t.get("decision"), t.get("decision"))
        lines.append(
            f"- 动量：{t.get('momentum')} · 宏观支撑：{t.get('macro_support')} · "
            f"估值：{t.get('valuation')} · 决策：**{dec}**"
        )
        r = t.get("reasoning") or {}
        if r.get("hypothesis"):
            lines.append(f"- 假设：{r['hypothesis']}")
        tid = t.get("id")
        sub_inds = (industries.get("by_theme") or {}).get(tid) or []
        if sub_inds:
            lines.append("- 细分行业：" + "、".join(
                f"{i.get('name_zh') or i.get('name')} {i.get('rating')}" for i in sub_inds[:5]
            ))
        lines.append("")

    lines.append("### 弱势主题")
    for w in themes.get("weak_themes") or []:
        lines.append(f"- {w.get('name_zh') or w.get('name')} — {w.get('reason')}")

    lines.extend(["", "---", "", "## 3. 行业轮动（Industry）", ""])
    for ind in (industries.get("top_industries") or [])[:8]:
        lines.append(f"### {ind.get('name_zh') or ind.get('name')} {ind.get('rating')}")
        lines.append(
            f"趋势：{ind.get('trend')} · 催化剂：{ind.get('catalyst')} · "
            f"估值：{ind.get('valuation')} · 风险：{ind.get('risk')}"
        )
        reps = ", ".join(ind.get("representative_stocks") or [])
        if reps:
            lines.append(f"代表标的：{reps}")
        lines.append("")

    lines.extend(["---", "", "## 4. 个股排序（Stock）", ""])
    by_ind = stocks.get("by_industry") or {}
    shown = 0
    for iname, lst in by_ind.items():
        if shown >= 4:
            break
        lines.append(f"### {iname}")
        for s in lst[:2]:
            lines.append(
                f"**{s['ticker']}** {s.get('rating')} — "
                f"{'；'.join(s.get('why') or [])} · 估值：{s.get('valuation')} · "
                f"置信度：{s.get('confidence')}"
            )
        lines.append("")
        shown += 1

    lines.extend(["---", "", "## 5. 组合构建（Portfolio）", "", "### 战略配置（仅美股）", ""])
    lines.append("| 资产 | 权重 | 参考标的 |")
    lines.append("|------|------|----------|")
    label_zh = {"US Equity": "美股", "Bonds": "债券", "Gold": "黄金", "Cash": "现金"}
    for row in portfolio.get("strategic_allocation") or []:
        lbl = label_zh.get(row.get("label", ""), row.get("label"))
        lines.append(f"| {lbl} | {row.get('weight_pct')}% | {row.get('proxy') or '—'} |")

    lines.extend(["", "### 战术倾斜", ""])
    for t in portfolio.get("active_tilts") or []:
        name = t.get("target_zh") or t.get("target")
        lines.append(f"- {t.get('direction')}{t.get('tilt_pct')}% {name}")

    lines.append("")
    lines.append("**ETF 实现：** " + ", ".join(portfolio.get("etf_implementation") or []))
    if portfolio.get("stock_sleeve"):
        lines.append("")
        lines.append("**股票仓位：** " + ", ".join(
            f"{s['ticker']}（{s['weight_pct']}%）" for s in portfolio["stock_sleeve"]
        ))

    lines.extend(["", "---", "", "## 6. 情景规划（Scenario）", ""])
    for sc in scenarios.get("scenarios") or []:
        lines.append(f"**{sc.get('name_zh') or sc.get('name')}**（{sc.get('probability_pct')}%）— {sc.get('narrative_zh') or sc.get('narrative')}")
        lines.append(f"- 组合动作：{sc.get('portfolio_action')}")
        lines.append("")

    lines.extend(["---", "", "## 7. 触发引擎（If → Then）", ""])
    for tr in triggers.get("triggers") or []:
        flag = "**【已触发】** " if tr.get("active") else ""
        lines.append(f"{flag}**若** {tr.get('if')}")
        for step in tr.get("then") or []:
            lines.append(f"  → {step}")
        lines.append("")

    lines.extend(["---", "", "## 8. 监控面板", "", "### 市场健康度", ""])
    dim_zh = {
        "breadth": "广度",
        "credit": "信用",
        "liquidity": "流动性",
        "valuation": "估值",
        "momentum": "动量",
    }
    for dim, data in (monitor.get("market_health") or {}).items():
        if isinstance(data, dict):
            lines.append(f"- **{dim_zh.get(dim, dim)}** {data.get('rating')}（{data.get('score')}）")

    lines.extend(["", "### 关注日历", ""])
    earnings = monitor.get("earnings_calendar") or []
    if earnings:
        lines.append("**财报日历（Finnhub）：**")
        for w in earnings:
            imp = {"very_high": "极高", "high": "高", "medium": "中"}.get(w.get("importance", ""), w.get("importance"))
            theme = w.get("theme_zh") or w.get("theme") or ""
            ind = w.get("industry_zh") or w.get("industry") or ""
            ctx = f" · {theme}/{ind}" if theme else ""
            lines.append(
                f"- **{w.get('ticker')}** {w.get('date')}（{w.get('hour')}）— "
                f"{w.get('timing')} · 重要性：{imp}{ctx}"
            )
        lines.append("")
    for w in monitor.get("macro_watch") or monitor.get("watch_list") or []:
        if w.get("source") == "finnhub_earnings":
            continue
        imp = {"high": "高", "medium": "中", "very_high": "极高"}.get(w.get("importance", ""), w.get("importance"))
        lines.append(f"- **{w.get('event')}** — {w.get('timing')} · 重要性：{imp}")

    lines.extend(["", note(cio.get("disclaimer_zh") or cio.get("disclaimer", ""))])
    return "\n".join(lines)


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)
