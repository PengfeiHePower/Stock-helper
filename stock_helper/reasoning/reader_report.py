from __future__ import annotations

from typing import Any

from stock_helper.analysis.formatting import fmt_num, note


def _conviction_label(score: float | None) -> str:
    if score is None:
        return "Moderate"
    if score >= 0.65:
        return "High"
    if score >= 0.45:
        return "Low–moderate"
    return "Low"


def _market_tone(reasoning: dict[str, Any]) -> str:
    conflict = reasoning.get("conflict") or {}
    macro = (reasoning.get("layer_signals") or {}).get("macro", {})
    bd = reasoning.get("breadth_deep") or {}
    if (bd.get("leadership_score") or 0) >= 0.7:
        return "Constructive, but narrowly led"
    if macro.get("direction") == "bullish" and conflict.get("level") == "low":
        return "Constructive"
    if conflict.get("level") == "high":
        return "Cautious"
    return "Constructive, but fragile"


def _view_status_label(thesis_status: dict[str, Any]) -> str:
    st = thesis_status.get("status", "HOLD")
    if st == "INVALIDATED":
        return "under review"
    if st == "WEAKEN" and (thesis_status.get("likelihood_delta") or 0) <= -0.05:
        return "softening"
    return "unchanged"


def _human_evidence_rows(reasoning: dict[str, Any]) -> list[dict[str, str]]:
    bd = reasoning.get("breadth_deep") or {}
    rets = bd.get("returns") or {}
    rows: list[dict[str, str]] = []

    mag7 = bd.get("mag7_avg_day_pct")
    if mag7 is not None:
        rows.append(
            {
                "evidence": "Magnificent Seven (avg)",
                "reading": f"{mag7:+.2f}%",
                "implication": "Mega-caps led the tape",
            }
        )
    for label, key in (
        ("S&P 500", "SPY"),
        ("Nasdaq-100", "QQQ"),
        ("Russell 2000", "IWM"),
        ("Equal-weight S&P", "RSP"),
    ):
        v = rets.get(key)
        if v is not None:
            impl = ""
            if key == "IWM" and rets.get("SPY") is not None and v < rets["SPY"] - 0.15:
                impl = "Small-cap risk appetite weak"
            elif key == "RSP" and bd.get("rsp_spy_spread") is not None:
                sp = bd["rsp_spy_spread"]
                impl = "Breadth slightly narrow" if sp < -0.05 else "Participation in line"
            rows.append({"evidence": label, "reading": f"{v:+.2f}%", "implication": impl or "—"})

    rsp_sp = bd.get("rsp_spy_spread")
    if rsp_sp is not None:
        rows.append(
            {
                "evidence": "RSP minus SPY",
                "reading": f"{rsp_sp:+.2f} pp",
                "implication": "Narrow" if rsp_sp < -0.05 else "Broad enough",
            }
        )
    return rows


def _reader_takeaway(reasoning: dict[str, Any], snapshot: dict[str, Any]) -> list[str]:
    """One-line + supporting paragraphs — no raw keys."""
    regime = snapshot.get("regime") or {}
    dims = regime.get("dimension_labels") or {}
    bd = reasoning.get("breadth_deep") or {}
    ind = regime.get("indicators") or {}
    hy = reasoning.get("hypotheses") or {}
    best = _reader_best_explanation(hy, bd)

    status = _view_status_label(reasoning.get("thesis_status") or {})
    lines = [
        "**The takeaway**",
        "",
        f"**Market view {status}:** the rally remains supported by firm growth and calm credit, "
        f"but participation is uneven — mega-caps are doing the heavy lifting while smaller names lag.",
        "",
        "US equities stay underpinned by **firm growth** and **tight credit spreads**, "
        "yet leadership is concentrated. Investors appear to favor liquid mega-cap names "
        "over broader market beta.",
        "",
    ]

    ten_y = ind.get("ten_year_yield")
    if ten_y and float(ten_y) >= 4.0:
        lines.append(
            f"**Elevated Treasury yields** ({ten_y}%) remain a structural constraint on growth "
            f"valuations. Today's tape points more clearly to **narrow participation** than to a "
            f"broad technology selloff — QQQ is only modestly behind SPY."
        )
    else:
        lines.append(
            "Today's clearest signal is **selective risk appetite**: large caps advance while "
            "small caps struggle to keep pace."
        )

    if best:
        lines.extend(["", f"**Best read:** {best['summary']}"])
        if best.get("alt"):
            lines.append(f"**Alternative:** {best['alt']}")
        if best.get("invalidate"):
            lines.append(f"**What would change this view:** {best['invalidate']}")

    _ = dims  # reserved for future tightening
    return lines


def _reader_best_explanation(hyp: dict[str, Any], bd: dict[str, Any]) -> dict[str, str]:
    mag7 = bd.get("mag7_avg_day_pct")
    iwm_sp = bd.get("iwm_spy_spread")
    leadership = bd.get("leadership_score") or 0

    if leadership >= 0.65 and iwm_sp is not None and float(iwm_sp) < -0.3:
        summary = (
            "Selective risk appetite — investors favored liquid mega-cap AI names "
            "while avoiding smaller, more rate-sensitive companies."
        )
        alt = (
            "Elevated yields may also be limiting broader growth participation, "
            "though mega-caps are not showing broad tech weakness today."
        )
        invalidate = "A sustained rebound in small caps and equal-weight indices."
        return {"summary": summary, "alt": alt, "invalidate": invalidate}

    sel = hyp.get("selected") or {}
    return {
        "summary": sel.get("label", "Mixed drivers — no single dominant explanation."),
        "alt": "",
        "invalidate": "Watch for a shift in sector leadership or credit conditions.",
    }


def _reader_what_changed(reasoning: dict[str, Any], *, biweekly: bool) -> list[str]:
    period = "over the past two weeks" if biweekly else "since the last report"
    lines = [f"## What changed {period}", ""]

    diff = reasoning.get("hypothesis_diff") or {}
    changes = [c for c in (reasoning.get("what_changed") or []) if c.get("changed")]
    baseline = not diff.get("has_prior") and len(changes) <= 1

    if baseline:
        lines.append(
            "This is the **baseline edition**. Trend comparisons begin with the next report."
        )
        lines.append("")
        lines.append("**Current snapshot highlights:**")
        bd = reasoning.get("breadth_deep") or {}
        rets = bd.get("returns") or {}
        if rets.get("SPY") is not None:
            lines.append(f"- S&P 500 {rets['SPY']:+.2f}% · Nasdaq-100 {rets.get('QQQ', 0):+.2f}%")
        if bd.get("mag7_avg_day_pct") is not None:
            lines.append(f"- Magnificent Seven average {bd['mag7_avg_day_pct']:+.2f}%")
        if rets.get("IWM") is not None:
            lines.append(f"- Russell 2000 {rets['IWM']:+.2f}%")
        lines.append("")
        return lines

    unchanged_labels = [c for c in (reasoning.get("what_changed") or []) if not c.get("changed")]
    if unchanged_labels:
        lines.append("**Unchanged**")
        for c in unchanged_labels[:4]:
            if c.get("field") == "baseline":
                continue
            lines.append(f"- {c.get('label', c.get('field'))}: {c.get('current', '—')}")
        lines.append("")

    if changes:
        lines.append("**Changed**")
        for c in changes:
            if c.get("field") == "baseline":
                continue
            lines.append(f"- **{c.get('label')}:** {c.get('prior', '—')} → {c.get('current', '—')}")
            if c.get("note"):
                lines.append(f"  {c['note']}")
        lines.append("")

    if diff.get("has_prior") and diff.get("summary"):
        movers = [d for d in (diff.get("diffs") or []) if d.get("direction") in ("up", "down")]
        if movers:
            lines.append("**Explanation layer:**")
            for d in movers[:2]:
                lines.append(
                    f"- {d['label']}: evidence score "
                    f"{fmt_num(d.get('prior_likelihood'), 2)} → {fmt_num(d.get('current_likelihood'), 2)}"
                )
            lines.append("")

    if not changes and diff.get("has_prior"):
        lines.append("No material change in the overall market regime or dominant narrative.")
        lines.append("")

    return lines


def _reader_three_forces(reasoning: dict[str, Any]) -> list[str]:
    lines = ["## Three forces shaping the market", ""]
    for i, d in enumerate((reasoning.get("top_drivers") or [])[:3], 1):
        inv = _driver_invalidate(d.get("id", ""))
        lines.append(f"**{i}. {d.get('label')}** ({d.get('direction', 'neutral')})")
        if d.get("detail"):
            lines.append(f"- {d['detail']}")
        if inv:
            lines.append(f"- *What could change this:* {inv}")
        lines.append("")
    return lines


def _driver_invalidate(driver_id: str) -> str:
    return {
        "dominant_narrative": "Weaker AI earnings guidance or slower capex growth.",
        "inflation": "Inflation surprises to the downside and Fed easing odds rise.",
        "treasury_yield": "Yields fall on soft data; growth multiples re-rate higher.",
        "breadth": "Equal-weight and small caps begin to outperform.",
        "growth_vs_broad": "QQQ reclaims leadership vs SPY for multiple sessions.",
        "credit_risk": "HY spreads widen materially.",
    }.get(driver_id, "")


def _reader_key_tension(reasoning: dict[str, Any], snapshot: dict[str, Any]) -> list[str]:
    conflict = reasoning.get("conflict") or {}
    dims = (snapshot.get("regime") or {}).get("dimension_labels") or {}
    ind = (snapshot.get("regime") or {}).get("indicators") or {}
    bd = reasoning.get("breadth_deep") or {}

    supports: list[str] = []
    limits: list[str] = []

    if dims.get("growth") == "firm":
        supports.append("Firm growth")
    if dims.get("risk") in ("calm", "moderate"):
        supports.append("Calm volatility")
    if ind.get("hy_spread") and float(ind["hy_spread"]) < 4:
        supports.append("Tight credit spreads")

    if dims.get("inflation") in ("elevated", "moderate"):
        limits.append("Sticky inflation")
    if ind.get("ten_year_yield") and float(ind["ten_year_yield"]) >= 4:
        limits.append(f"Elevated Treasury yields ({ind['ten_year_yield']}%)")
    if (bd.get("iwm_spy_spread") or 0) < -0.3:
        limits.append("Weak small-cap participation")

    lines = ["## The market's key tension", ""]
    lines.append(
        "Firm growth and calm credit conditions support equities, "
        "but sticky inflation and elevated yields limit broader participation."
    )
    lines.append("")

    lines.append("| Supports the market | Limits the market |")
    lines.append("|---------------------|-------------------|")
    for i in range(max(len(supports), len(limits))):
        s = supports[i] if i < len(supports) else ""
        l = limits[i] if i < len(limits) else ""
        lines.append(f"| {s} | {l} |")
    lines.append("")

    res = conflict.get("resolution") or {}
    if res.get("statement"):
        lines.append(
            "**For now:** the positive macro backdrop is winning, but only narrowly."
        )
    lines.append("")
    return lines


def _reader_participation(reasoning: dict[str, Any]) -> list[str]:
    lines = ["## Market participation", ""]
    rows = _human_evidence_rows(reasoning)
    if not rows:
        return []

    lines.append("| Evidence | Reading | Implication |")
    lines.append("|----------|---------|-------------|")
    for r in rows:
        lines.append(f"| {r['evidence']} | {r['reading']} | {r['implication']} |")
    lines.append("")

    bd = reasoning.get("breadth_deep") or {}
    if bd.get("interpretation"):
        lines.append(bd["interpretation"])
        lines.append("")
    return lines


def _reader_narrative_pulse(reasoning: dict[str, Any]) -> list[str]:
    block = reasoning.get("narrative_block") or {}
    narratives = block.get("narratives") or []
    if not narratives:
        return []

    lines = ["## Narrative pulse", ""]
    if narratives:
        lines.append(f"- **Dominant theme:** {narratives[0].get('headline', '—')}")
    if len(narratives) > 1:
        lines.append(f"- **Secondary concern:** {narratives[1].get('headline', '—')}")
    if len(narratives) > 2:
        lines.append(f"- **Emerging risk:** {narratives[2].get('headline', '—')}")

    shift = block.get("narrative_shift") or {}
    if shift.get("note"):
        lines.append(f"- **Narrative shift:** {shift['note']}")
    top = narratives[0] if narratives else {}
    if top.get("stage"):
        lines.append(
            f"- **AI narrative stage:** {top.get('stage')} "
            f"(path: {top.get('evolution_path', '—')})"
        )
    lines.append("")
    return lines


def _reader_watch_next(reasoning: dict[str, Any]) -> list[str]:
    lines = ["## What to watch next", ""]
    scenarios = reasoning.get("scenarios") or []
    uncertainties = reasoning.get("uncertainties") or []

    lines.append("The current view would **strengthen** if equal-weight and small-cap indices outperform.")
    lines.append("")
    lines.append("It would **weaken** if:")
    for u in uncertainties:
        if u.get("thesis_breaker"):
            lines.append(f"- {u.get('label')}")
    for s in scenarios:
        if s.get("thesis_impact") == "invalidates":
            lines.append(f"- {s.get('trigger')}")
    lines.append("")

    if scenarios:
        lines.append("**Scenarios**")
        for s in scenarios[:3]:
            lines.append(
                f"- {s.get('trigger')} (~{s.get('probability_pct', '—')}%): "
                f"{' → '.join(s.get('path') or [])}"
            )
        lines.append("")
    return lines


def _moka_explains(snapshot: dict[str, Any]) -> list[str]:
    regime = snapshot.get("regime") or {}
    dims = regime.get("dimension_labels") or {}
    lines = [
        "## Moka explains",
        "",
        f"Think of the market like weather: we're in **{regime.get('regime', 'mixed').replace('_', ' ')}** — "
        f"growth is **{dims.get('growth', '?')}**, inflation is **{dims.get('inflation', '?')}**, "
        f"and the Fed looks **{dims.get('policy', '?')}**.",
        "",
        "The headline index can look fine while only a few huge stocks do the work — "
        "like a team winning because one star player scored all the points. "
        "Watch whether smaller stocks start joining the rally.",
        "",
    ]
    return lines


def format_reader_markdown(
    reasoning: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    biweekly: bool = True,
    lang: str = "en",
) -> str:
    """Investor-facing market note — lang: en | zh | both (zh first)."""
    if lang == "zh":
        from stock_helper.reasoning.reader_report_zh import format_reader_markdown_zh

        return format_reader_markdown_zh(reasoning, snapshot, biweekly=biweekly)
    if lang == "both":
        from stock_helper.reasoning.reader_report_zh import format_reader_markdown_zh

        zh = format_reader_markdown_zh(reasoning, snapshot, biweekly=biweekly)
        en = format_reader_markdown(reasoning, snapshot, biweekly=biweekly, lang="en")
        return f"{zh}\n\n---\n\n{en}"
    return _format_reader_markdown_en(reasoning, snapshot, biweekly=biweekly)


def _format_reader_markdown_en(
    reasoning: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    biweekly: bool = True,
) -> str:
    """English reader view."""
    thesis = reasoning.get("thesis") or {}
    regime_detail = reasoning.get("regime_detail") or {}
    regime = snapshot.get("regime") or {}

    conviction = _conviction_label(thesis.get("overall_confidence"))
    regime_conf = _conviction_label(regime.get("confidence"))

    lines = [
        "## Market at a glance",
        "",
        f"**Regime:** {regime_detail.get('label', '—')}",
        f"**Market tone:** {_market_tone(reasoning)}",
        f"**Conviction:** {conviction} *(thesis)* · **Regime confidence:** {regime_conf}",
        f"**Main vulnerability:** The rally remains dependent on mega-cap earnings leadership.",
        "",
        f"*Conviction is {conviction.lower()} because breadth is session-level and "
        f"rate causality is not fully confirmed in today's price action.*",
        "",
    ]

    lines.extend(_reader_what_changed(reasoning, biweekly=biweekly))
    lines.extend(_reader_takeaway(reasoning, snapshot))
    lines.extend(_reader_three_forces(reasoning))
    lines.extend(_reader_key_tension(reasoning, snapshot))
    lines.extend(_reader_participation(reasoning))
    lines.extend(_reader_narrative_pulse(reasoning))
    lines.extend(_reader_watch_next(reasoning))
    lines.extend(_moka_explains(snapshot))
    lines.append(note("For informational purposes only. Not investment advice."))
    return "\n".join(lines)
