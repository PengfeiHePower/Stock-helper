from __future__ import annotations

from typing import Any

from stock_helper.analysis.factors import momentum_proxy
from stock_helper.collectors.fundamentals import load_fundamentals_map
from stock_helper.config import load_yaml


def _day_return(quote: dict) -> float | None:
    dp = quote.get("dp")
    if dp is not None:
        return round(float(dp), 2)
    c, pc = quote.get("c"), quote.get("pc")
    if c is not None and pc and pc != 0:
        return round((float(c) - float(pc)) / float(pc) * 100, 2)
    return None


def analyze_breadth_deep(
    structure: dict[str, Any],
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    """Deeper participation: RSP/SPY/IWM, sector day moves, Mag7 concentration."""
    cfg = load_yaml("structure.yaml")
    eq = (cfg.get("breadth") or {}).get("equal_weight", "RSP")
    cap = (cfg.get("breadth") or {}).get("cap_weight", "SPY")
    growth = (cfg.get("growth_vs_broad") or {}).get("growth", "QQQ")
    sectors = list(cfg.get("sector_etfs") or [])
    mag7 = [m["ticker"] for m in (cfg.get("mag7") or [])]

    tickers = list(dict.fromkeys([cap, eq, "IWM", growth] + sectors + mag7))
    data = load_fundamentals_map(tickers, refresh=refresh)

    def _quote_ret(sym: str) -> float | None:
        funds = data.get(sym.upper())
        if not funds:
            return None
        return _day_return(funds.get("quote") or {})

    spy_ret = _quote_ret(cap)
    rsp_ret = _quote_ret(eq)
    iwm_ret = _quote_ret("IWM")
    qqq_ret = _quote_ret(growth)

    participation_score = _participation_score(spy_ret, rsp_ret, iwm_ret)

    sector_moves: list[dict[str, Any]] = []
    for etf in sectors:
        ret = _quote_ret(etf)
        if ret is None:
            continue
        sector_moves.append(
            {
                "etf": etf.upper(),
                "day_change_pct": ret,
                "vs_spy": None if spy_ret is None else round(ret - spy_ret, 2),
            }
        )
    sector_moves.sort(key=lambda x: x.get("day_change_pct") or 0, reverse=True)

    mag7_moves = []
    for t in mag7:
        funds = data.get(t.upper())
        if not funds:
            continue
        quote = funds.get("quote") or {}
        metric = funds.get("metric") or {}
        mag7_moves.append(
            {
                "ticker": t,
                "day_change_pct": _day_return(quote),
                "momentum_52w": momentum_proxy(quote, metric),
            }
        )

    mag7_avg = _avg([m["day_change_pct"] for m in mag7_moves if m["day_change_pct"] is not None])
    tech_share = _tech_contribution_estimate(sector_moves, spy_ret)
    leadership_score = _leadership_score(mag7_avg, spy_ret, mag7_moves)
    breadth_score = _breadth_score(sector_moves, spy_ret)
    sector_participation = _sector_participation(sector_moves, spy_ret)

    interpretation = _interpret(
        spy_ret, rsp_ret, iwm_ret, participation_score, mag7_avg, tech_share, sector_moves
    )

    return {
        "participation_score": participation_score,
        "leadership_score": leadership_score,
        "breadth_score": breadth_score,
        "sector_participation_pct": sector_participation,
        "returns": {
            "SPY": spy_ret,
            "RSP": rsp_ret,
            "IWM": iwm_ret,
            "QQQ": qqq_ret,
        },
        "rsp_spy_spread": None if spy_ret is None or rsp_ret is None else round(rsp_ret - spy_ret, 2),
        "iwm_spy_spread": None if spy_ret is None or iwm_ret is None else round(iwm_ret - spy_ret, 2),
        "sector_day_leaders": sector_moves[:3],
        "sector_day_laggards": list(reversed(sector_moves[-3:])) if len(sector_moves) >= 3 else [],
        "tech_contribution_estimate_pct": tech_share,
        "mag7_avg_day_pct": mag7_avg,
        "mag7_moves": mag7_moves,
        "interpretation": interpretation,
        "signal": _breadth_signal(participation_score, structure),
    }


def _avg(vals: list[float]) -> float | None:
    if not vals:
        return None
    return round(sum(vals) / len(vals), 2)


def _leadership_score(
    mag7_avg: float | None,
    spy: float | None,
    mag7_moves: list[dict],
) -> float | None:
    if mag7_avg is None or spy is None:
        return None
    spread = float(mag7_avg) - float(spy)
    positive_mag7 = sum(1 for m in mag7_moves if (m.get("day_change_pct") or 0) > 0)
    share = positive_mag7 / max(len(mag7_moves), 1)
    raw = 0.5 + spread * 0.15 + share * 0.35
    return round(max(0.0, min(1.0, raw)), 2)


def _breadth_score(sector_moves: list[dict], spy: float | None) -> float | None:
    if not sector_moves or spy is None:
        return None
    beating = sum(1 for s in sector_moves if (s.get("day_change_pct") or 0) > spy)
    return round(beating / len(sector_moves), 2)


def _sector_participation(sector_moves: list[dict], spy: float | None) -> float | None:
    if not sector_moves or spy is None:
        return None
    beating = sum(1 for s in sector_moves if (s.get("vs_spy") or 0) > 0)
    return round(100.0 * beating / len(sector_moves), 0)


def _participation_score(
    spy: float | None,
    rsp: float | None,
    iwm: float | None,
) -> float | None:
    if spy is None:
        return None
    score = 50.0
    if rsp is not None:
        score += (rsp - spy) * 8
    if iwm is not None:
        score += (iwm - spy) * 5
    return round(max(0.0, min(100.0, score)), 1)


def _tech_contribution_estimate(
    sector_moves: list[dict[str, Any]],
    spy_ret: float | None,
) -> float | None:
    if spy_ret is None or abs(spy_ret) < 0.05:
        return None
    xlk = next((s for s in sector_moves if s["etf"] == "XLK"), None)
    if not xlk or xlk.get("day_change_pct") is None:
        return None
    # XLK ≈ 30% of S&P tech weight; rough narrative contribution
    est = min(95.0, max(5.0, abs(float(xlk["day_change_pct"])) / max(abs(spy_ret), 0.1) * 35))
    return round(est, 0)


def _breadth_signal(score: float | None, structure: dict[str, Any]) -> str:
    base = (structure.get("breadth") or {}).get("signal", "mixed")
    if score is None:
        return base
    if score < 35:
        return "narrow_rally"
    if score > 65:
        return "broad_participation"
    return base if base != "unknown" else "mixed"


def _interpret(
    spy: float | None,
    rsp: float | None,
    iwm: float | None,
    participation: float | None,
    mag7_avg: float | None,
    tech_share: float | None,
    sectors: list[dict[str, Any]],
) -> str:
    parts: list[str] = []
    if spy is not None and rsp is not None:
        if rsp < spy - 0.2:
            parts.append(f"SPY {spy:+.2f}% but RSP {rsp:+.2f}% — mega-caps doing the heavy lifting.")
        elif rsp > spy + 0.15:
            parts.append(f"Equal-weight ({rsp:+.2f}%) beating cap-weight ({spy:+.2f}%) — broad participation.")
    if iwm is not None and spy is not None and iwm < spy - 0.25:
        parts.append(f"Small caps (IWM {iwm:+.2f}%) lagging — risk appetite selective.")
    if tech_share is not None and tech_share >= 50:
        parts.append(f"Technology may account for ~{tech_share:.0f}% of index move (XLK-led estimate).")
    if mag7_avg is not None and spy is not None and mag7_avg > spy + 0.2:
        parts.append(f"Mag7 average ({mag7_avg:+.2f}%) above SPY — leadership concentrated.")
    if sectors:
        leader = sectors[0]
        parts.append(f"Sector leader today: {leader['etf']} ({leader.get('day_change_pct'):+.2f}%).")
    return " ".join(parts) if parts else "Participation metrics are mixed — no dominant breadth story today."
