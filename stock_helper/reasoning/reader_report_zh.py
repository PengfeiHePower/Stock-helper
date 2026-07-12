from __future__ import annotations

from typing import Any

from stock_helper.analysis.formatting import fmt_num, note


def _conviction_zh(score: float | None) -> str:
    if score is None:
        return "中等"
    if score >= 0.65:
        return "高"
    if score >= 0.45:
        return "中低"
    return "低"


def _tone_zh(reasoning: dict[str, Any]) -> str:
    bd = reasoning.get("breadth_deep") or {}
    if (bd.get("leadership_score") or 0) >= 0.7:
        return "偏积极，但行情偏窄"
    conflict = reasoning.get("conflict") or {}
    if conflict.get("level") == "high":
        return "谨慎"
    return "偏积极，但较脆弱"


def _view_status_zh(thesis_status: dict[str, Any]) -> str:
    st = thesis_status.get("status", "HOLD")
    if st == "INVALIDATED":
        return "需重新审视"
    if st == "WEAKEN" and (thesis_status.get("likelihood_delta") or 0) <= -0.05:
        return "有所减弱"
    return "基本不变"


def _regime_label_zh(label: str) -> str:
    return {
        "Late-cycle expansion": "晚期扩张",
        "Selective risk-on": "选择性风险偏好",
        "Liquidity-neutral": "流动性中性",
        "Expansion": "扩张",
        "Slowdown": "放缓",
        "Recovery": "复苏",
    }.get(label, label)


def _direction_zh(d: str) -> str:
    return {"tailwind": "顺风", "headwind": "逆风", "neutral": "中性"}.get(d, d)


def _evidence_rows_zh(reasoning: dict[str, Any]) -> list[dict[str, str]]:
    bd = reasoning.get("breadth_deep") or {}
    rets = bd.get("returns") or {}
    rows: list[dict[str, str]] = []

    mag7 = bd.get("mag7_avg_day_pct")
    if mag7 is not None:
        rows.append({"evidence": "科技七巨头（均值）", "reading": f"{mag7:+.2f}%", "implication": "大盘股主导行情"})
    for label, key, impl_fn in (
        ("标普500", "SPY", lambda v, r: "—"),
        ("纳斯达克100", "QQQ", lambda v, r: "—"),
        ("罗素2000小盘", "IWM", lambda v, r: "小盘风险偏好偏弱" if v < (r.get("SPY") or 0) - 0.15 else "—"),
        ("等权标普", "RSP", lambda v, r: "广度略窄" if (bd.get("rsp_spy_spread") or 0) < -0.05 else "参与度尚可"),
    ):
        v = rets.get(key)
        if v is not None:
            rows.append({"evidence": label, "reading": f"{v:+.2f}%", "implication": impl_fn(v, rets)})
    rsp_sp = bd.get("rsp_spy_spread")
    if rsp_sp is not None:
        rows.append(
            {
                "evidence": "等权标普 − 市值加权",
                "reading": f"{rsp_sp:+.2f} 个百分点",
                "implication": "偏窄" if rsp_sp < -0.05 else "尚可",
            }
        )
    return rows


def _best_explanation_zh(hyp: dict[str, Any], bd: dict[str, Any]) -> dict[str, str]:
    leadership = bd.get("leadership_score") or 0
    iwm_sp = bd.get("iwm_spy_spread")
    if leadership >= 0.65 and iwm_sp is not None and float(iwm_sp) < -0.3:
        return {
            "summary": "选择性风险偏好——资金青睐流动性好的 AI 巨头，回避更小、更利率敏感的公司。",
            "alt": "高收益率也可能压制更广泛的增长参与，但今日巨头并未出现广泛科技股抛售。",
            "invalidate": "等权指数与小盘股持续跑赢。",
        }
    sel = hyp.get("selected") or {}
    labels = {
        "selective_mega_cap": "选择性偏好 mega-cap",
        "rate_pressure": "利率/久期压制成长",
        "sector_rotation": "板块轮动远离成长",
        "profit_taking": "AI 拥挤交易获利了结",
        "idiosyncratic": "个股因素主导",
    }
    slug = sel.get("slug") or ""
    return {
        "summary": labels.get(slug, sel.get("label", "多重因素交织，暂无单一主导解释。")),
        "alt": "",
        "invalidate": "关注板块领导力或信用条件是否转向。",
    }


def _driver_label_zh(d: dict[str, Any]) -> str:
    mapping = {
        "dominant_narrative": "AI 仍是主导市场叙事",
        "inflation": f"CPI 同比 {d.get('label', '').split()[-1] if 'CPI' in d.get('label', '') else '通胀'}",
        "treasury_yield": "10年期国债收益率偏高",
        "breadth": "市场广度（等权 vs 市值加权）",
        "growth_vs_broad": "成长 vs 大盘相对表现",
        "credit_risk": "信用利差",
    }
    return mapping.get(d.get("id", ""), d.get("label", "—"))


def _driver_detail_zh(d: dict[str, Any]) -> str:
    details = {
        "dominant_narrative": "利好 XLK/QQQ/NVDA 链条；关注财报指引。",
        "inflation": "通胀路径影响美联储反应函数与利率预期。",
        "treasury_yield": "长端利率抬升压制估值，尤其成长板块。",
        "breadth": "行情是否广泛参与，决定反弹可持续性。",
        "growth_vs_broad": "科技成长相对大盘的领导力。",
        "credit_risk": "信用环境决定风险偏好与股权风险溢价。",
    }
    return details.get(d.get("id", ""), d.get("detail", ""))


def _driver_invalidate_zh(driver_id: str) -> str:
    return {
        "dominant_narrative": "AI 财报指引走弱或资本开支放缓。",
        "inflation": "通胀意外下行，降息预期升温。",
        "treasury_yield": "经济数据偏弱推低收益率，成长估值修复。",
        "breadth": "等权与小盘股开始持续跑赢。",
        "growth_vs_broad": "QQQ 连续多日跑赢 SPY。",
        "credit_risk": "高收益债利差明显走阔。",
    }.get(driver_id, "")


def _narrative_headline_zh(n: dict[str, Any]) -> str:
    topic = n.get("topic", "")
    headlines = {
        "ai": "AI 仍是市场主导叙事",
        "rates": "美联储与利率占据讨论中心",
        "inflation": "通胀数据备受关注",
        "tariff": "关税与贸易风险抬头",
        "earnings": "财报季驱动个股波动",
    }
    return headlines.get(topic, n.get("headline", "—"))


def _change_label_zh(field: str, label: str) -> str:
    m = {
        "Composite regime": "综合宏观阶段",
        "Dominant narrative": "主导叙事",
        "Breadth signal": "广度信号",
        "Conflict level": "层间分歧",
        "Policy stance": "政策立场",
        "Growth reading": "增长读数",
        "Top driver": "首要驱动",
        "Sentiment mood": "情绪基调",
    }
    return m.get(label, label)


def format_reader_markdown_zh(
    reasoning: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    biweekly: bool = True,
) -> str:
    thesis = reasoning.get("thesis") or {}
    regime_detail = reasoning.get("regime_detail") or {}
    regime = snapshot.get("regime") or {}
    ind = regime.get("indicators") or {}
    bd = reasoning.get("breadth_deep") or {}
    hy = reasoning.get("hypotheses") or {}

    conviction = _conviction_zh(thesis.get("overall_confidence"))
    regime_conf = _conviction_zh(regime.get("confidence"))
    period = "过去两周" if biweekly else "上次报告以来"

    lines = [
        "## 市场速览",
        "",
        f"**宏观阶段：** {_regime_label_zh(regime_detail.get('label', '—'))}",
        f"**市场基调：** {_tone_zh(reasoning)}",
        f"**观点把握度：** {conviction}（市场叙事）· **宏观把握度：** {regime_conf}",
        f"**主要脆弱点：** 行情仍高度依赖 mega-cap / AI 财报表现。",
        "",
        f"*把握度为{conviction}，因广度主要基于单日数据，利率因果链尚未在价格中得到充分确认。*",
        "",
        f"## 发生了什么变化（{period}）",
        "",
    ]

    diff = reasoning.get("hypothesis_diff") or {}
    changes = [c for c in (reasoning.get("what_changed") or []) if c.get("changed")]
    if not diff.get("has_prior") and len(changes) <= 1:
        lines.append("这是**基准版**。与上期对比将从下一次报告开始。")
        lines.append("")
        lines.append("**当前快照：**")
        rets = bd.get("returns") or {}
        if rets.get("SPY") is not None:
            lines.append(f"- 标普500 {rets['SPY']:+.2f}% · 纳斯达克100 {rets.get('QQQ', 0):+.2f}%")
        if bd.get("mag7_avg_day_pct") is not None:
            lines.append(f"- 科技七巨头均值 {bd['mag7_avg_day_pct']:+.2f}%")
        if rets.get("IWM") is not None:
            lines.append(f"- 罗素2000 {rets['IWM']:+.2f}%")
        lines.append("")
    else:
        unchanged = [c for c in (reasoning.get("what_changed") or []) if not c.get("changed")]
        if unchanged:
            lines.append("**未变**")
            for c in unchanged[:4]:
                if c.get("field") == "baseline":
                    continue
                lbl = _change_label_zh(c.get("field", ""), c.get("label", ""))
                lines.append(f"- {lbl}：{c.get('current', '—')}")
            lines.append("")
        if changes:
            lines.append("**有变化**")
            for c in changes:
                if c.get("field") == "baseline":
                    continue
                lbl = _change_label_zh(c.get("field", ""), c.get("label", ""))
                lines.append(f"- **{lbl}：** {c.get('prior', '—')} → {c.get('current', '—')}")
            lines.append("")
        if not changes and diff.get("has_prior"):
            lines.append("整体宏观阶段与主导叙事无重大变化。")
            lines.append("")

    status = _view_status_zh(reasoning.get("thesis_status") or {})
    best = _best_explanation_zh(hy, bd)
    lines.extend(
        [
            "## 核心结论",
            "",
            f"**市场判断{status}：** 增长稳健、信用环境尚可支撑股市，"
            f"但参与度不均——巨头抬指数，小盘股落后。",
            "",
            "美股仍受**稳健增长**与**偏紧信用利差**支撑，但行情领导力集中，"
            "资金更偏好流动性好的大盘股，而非广泛 beta。",
            "",
        ]
    )
    ten_y = ind.get("ten_year_yield")
    if ten_y and float(ten_y) >= 4.0:
        lines.append(
            f"**国债收益率偏高**（10年期 {ten_y}%）仍是成长估值的结构性约束。"
            f"今日盘面更清晰地指向**参与面偏窄**，而非科技股普遍下跌——"
            f"纳斯达克100仅略落后于标普500。"
        )
    else:
        lines.append("今日最清晰信号是**选择性风险偏好**：大盘涨、小盘跟不动。")
    lines.append("")
    lines.append(f"**最佳解释：** {best['summary']}")
    if best.get("alt"):
        lines.append(f"**备选解释：** {best['alt']}")
    lines.append(f"**何种情况会推翻上述判断：** {best['invalidate']}")
    lines.append("")

    lines.append("## 三大驱动")
    lines.append("")
    for i, d in enumerate((reasoning.get("top_drivers") or [])[:3], 1):
        inv = _driver_invalidate_zh(d.get("id", ""))
        lines.append(f"**{i}. {_driver_label_zh(d)}**（{_direction_zh(d.get('direction', 'neutral'))}）")
        detail = _driver_detail_zh(d)
        if detail:
            lines.append(f"- {detail}")
        if inv:
            lines.append(f"- *可能改变的因素：* {inv}")
        lines.append("")

    dims = regime.get("dimension_labels") or {}
    supports, limits = [], []
    if dims.get("growth") == "firm":
        supports.append("增长稳健")
    if dims.get("risk") in ("calm", "moderate"):
        supports.append("波动率平静")
    if ind.get("hy_spread") and float(ind["hy_spread"]) < 4:
        supports.append("信用利差偏紧")
    if dims.get("inflation") in ("elevated", "moderate"):
        limits.append("通胀仍偏高")
    if ind.get("ten_year_yield") and float(ind["ten_year_yield"]) >= 4:
        limits.append(f"国债收益率偏高（{ind['ten_year_yield']}%）")
    if (bd.get("iwm_spy_spread") or 0) < -0.3:
        limits.append("小盘股参与偏弱")

    lines.extend(
        [
            "## 核心矛盾",
            "",
            "增长与信用环境支撑股市，但通胀粘性及高收益率限制更广泛参与。",
            "",
            "| 支撑市场 | 制约市场 |",
            "|----------|----------|",
        ]
    )
    for i in range(max(len(supports), len(limits))):
        lines.append(f"| {supports[i] if i < len(supports) else ''} | {limits[i] if i < len(limits) else ''} |")
    lines.extend(["", "**目前来看：** 宏观利好略占上风，但优势很窄。", ""])

    lines.append("## 市场参与度")
    lines.append("")
    rows = _evidence_rows_zh(reasoning)
    if rows:
        lines.append("| 指标 | 读数 | 含义 |")
        lines.append("|------|------|------|")
        for r in rows:
            lines.append(f"| {r['evidence']} | {r['reading']} | {r['implication']} |")
        lines.append("")
    if bd.get("interpretation"):
        # one-line zh summary from numbers
        rets = bd.get("returns") or {}
        parts = []
        if rets.get("IWM") is not None and rets.get("SPY") is not None:
            if rets["IWM"] < rets["SPY"] - 0.2:
                parts.append(f"小盘（IWM {rets['IWM']:+.2f}%）落后大盘，风险偏好有选择性。")
        if bd.get("mag7_avg_day_pct") is not None:
            parts.append(f"科技七巨头均值 {bd['mag7_avg_day_pct']:+.2f}%，领导力集中。")
        lines.append(" ".join(parts) if parts else "")
        lines.append("")

    block = reasoning.get("narrative_block") or {}
    narratives = block.get("narratives") or []
    if narratives:
        lines.append("## 叙事脉搏")
        lines.append("")
        lines.append(f"- **主导主题：** {_narrative_headline_zh(narratives[0])}")
        if len(narratives) > 1:
            lines.append(f"- **次要关注：** {_narrative_headline_zh(narratives[1])}")
        if len(narratives) > 2:
            lines.append(f"- **新兴风险：** {_narrative_headline_zh(narratives[2])}")
        shift = block.get("narrative_shift") or {}
        if shift.get("changed"):
            lines.append(f"- **叙事切换：** 从 {shift.get('prior_main')} 转向 {shift.get('current_main')}")
        else:
            lines.append(f"- **叙事切换：** 无 · {shift.get('current_main', 'ai')} 仍占主导")
        top = narratives[0]
        stage_map = {
            "innovation": "创新",
            "capex": "资本开支",
            "profitability": "盈利兑现",
            "valuation": "估值",
            "beats": "业绩超预期",
            "guidance": "指引",
            "margins": "利润率",
        }
        if top.get("stage"):
            stage = stage_map.get(top["stage"], top["stage"])
            lines.append(f"- **AI 叙事阶段：** {stage}")
        lines.append("")

    lines.extend(["## 接下来关注什么", ""])
    lines.append("若等权指数与小盘股持续跑赢，当前判断将**强化**。")
    lines.append("")
    lines.append("若出现以下情况，判断将**弱化**：")
    for u in reasoning.get("uncertainties") or []:
        if u.get("thesis_breaker"):
            labels = {
                "ai_guidance": "AI / 巨头财报指引",
                "next_cpi": "下一次 CPI / PCE",
                "fed_tone": "美联储表态",
                "tariff_escalation": "关税升级",
            }
            lines.append(f"- {labels.get(u.get('id', ''), u.get('label', ''))}")
    for s in reasoning.get("scenarios") or []:
        if s.get("thesis_impact") == "invalidates":
            triggers = {
                "cpi_higher": "CPI 高于预期",
                "earnings_miss": "AI 财报不及预期",
                "risk_off": "VIX 飙升 / 信用走阔",
            }
            lines.append(f"- {triggers.get(s.get('id', ''), s.get('trigger', ''))}")
    lines.append("")

    scenarios = reasoning.get("scenarios") or []
    if scenarios:
        lines.append("**情景分支**")
        for s in scenarios[:3]:
            triggers = {
                "cpi_lower": "CPI 低于预期",
                "cpi_higher": "CPI 高于预期",
                "earnings_miss": "AI 财报失望",
            }
            t = triggers.get(s.get("id", ""), s.get("trigger", ""))
            lines.append(f"- {t}（约 {s.get('probability_pct', '—')}%）")
        lines.append("")

    growth = {"firm": "稳健", "slowing": "放缓", "mixed": "混合"}.get(
        dims.get("growth", ""), dims.get("growth", "—")
    )
    inflation = {"elevated": "偏高", "moderate": "温和", "cooling": "回落"}.get(
        dims.get("inflation", ""), dims.get("inflation", "—")
    )
    policy = {"neutral_tight": "中性偏紧", "restrictive": "紧缩", "accommodative": "宽松"}.get(
        dims.get("policy", ""), dims.get("policy", "—")
    )
    lines.extend(
        [
            "## Moka 白话",
            "",
            f"可以把市场想成天气：当前处于**{regime.get('regime', 'mixed').replace('_', ' ')}**——"
            f"增长**{growth}**、通胀**{inflation}**、美联储立场**{policy}**。",
            "",
            "指数看起来不错，可能只是少数巨头在扛——像球队赢球全靠一个球星。"
            "留意小盘股会不会后来居上、行情会不会变得更「广泛」。",
            "",
            note("仅供参考，不构成投资建议。"),
        ]
    )
    return "\n".join(lines)
