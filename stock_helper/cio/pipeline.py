from __future__ import annotations

from datetime import date
from typing import Any

from stock_helper.cio.industries import build_industry_rotation
from stock_helper.cio.monitoring import build_monitoring_dashboard
from stock_helper.cio.portfolio import build_portfolio
from stock_helper.cio.regime import build_regime_layer
from stock_helper.cio.scenarios import build_scenario_planning
from stock_helper.cio.stocks import build_stock_ranking
from stock_helper.cio.themes import build_theme_rotation
from stock_helper.cio.triggers import build_trigger_engine
from stock_helper.config import load_yaml


def build_cio_pipeline(
    snapshot: dict[str, Any],
    *,
    risk_level: str | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """
    CIO Investment Agent — full decision pipeline.
    Market → Theme → Industry → Stock → Portfolio → Scenario → Triggers → Monitor
    """
    level = risk_level or load_yaml("cio.yaml").get("default_risk_level", "L2")

    regime_layer = build_regime_layer(snapshot)
    theme_layer = build_theme_rotation(snapshot, refresh=refresh)
    industry_layer = build_industry_rotation(snapshot, theme_layer, refresh=refresh)
    stock_layer = build_stock_ranking(snapshot, industry_layer, refresh=refresh)
    portfolio_layer = build_portfolio(
        snapshot, regime_layer, theme_layer, stock_layer, risk_level=level
    )
    scenario_layer = build_scenario_planning(snapshot, portfolio_layer)
    trigger_layer = build_trigger_engine(snapshot)
    monitor_layer = build_monitoring_dashboard(
        snapshot,
        industry_layer=industry_layer,
        stock_layer=stock_layer,
    )

    executive = _executive_summary(
        regime_layer, theme_layer, portfolio_layer, trigger_layer, monitor_layer
    )

    return {
        "version": 2,
        "as_of_date": date.today().isoformat(),
        "risk_level": level,
        "executive_summary": executive,
        "regime": regime_layer,
        "theme_rotation": theme_layer,
        "industry_rotation": industry_layer,
        "stock_ranking": stock_layer,
        "portfolio": portfolio_layer,
        "scenarios": scenario_layer,
        "triggers": trigger_layer,
        "monitoring": monitor_layer,
        "disclaimer": "US equities only. Educational investment reasoning — not personalized advice.",
        "disclaimer_zh": "仅美股。教育性投资推理，非个性化投资建议。",
    }


def _executive_summary(
    regime: dict,
    themes: dict,
    portfolio: dict,
    triggers: dict,
    monitor: dict,
) -> dict[str, Any]:
    dom = themes.get("dominant_theme") or {}
    active = triggers.get("active_triggers") or []
    health = monitor.get("market_health") or {}

    en = (
        f"Regime: {regime.get('current_regime')} ({regime.get('confidence_label', 'Moderate')} confidence). "
        f"Lead theme: {dom.get('name', '—')} ({dom.get('rating', '')}). "
        f"US equity strategic weight {portfolio.get('weights', {}).get('us_equity', '—')}%. "
        f"{len(active)} active trigger(s)."
    )
    zh = (
        f"市场阶段：{regime.get('current_regime_zh') or regime.get('current_regime')}（"
        f"把握度{regime.get('confidence_label', '中等')}）。"
        f"主线主题：{dom.get('name_zh') or dom.get('name', '—')}（{dom.get('rating', '')}）。"
        f"美股战略仓位 {portfolio.get('weights', {}).get('us_equity', '—')}%。"
        f"已触发 {len(active)} 条规则。"
    )
    return {
        "text_en": en,
        "text_zh": zh,
        "lead_theme": dom.get("id"),
        "risk_posture": _health_posture(health),
    }


def _health_posture(health: dict) -> str:
    scores = [v.get("score", 50) for v in health.values() if isinstance(v, dict)]
    avg = sum(scores) / len(scores) if scores else 50
    if avg >= 70:
        return "Constructive"
    if avg >= 55:
        return "Mixed"
    return "Fragile"
