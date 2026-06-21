from __future__ import annotations

from typing import Any

from stock_helper.config import load_yaml
from stock_helper.storage.db import CostLog, get_session

# Approximate USD per 1M tokens (Plan A models, mid-2026 estimates)
PRICING: dict[str, tuple[float, float]] = {
    "gemini/gemini-2.5-flash-lite": (0.10, 0.40),
    "anthropic/claude-sonnet-4-6": (3.0, 15.0),
    "gpt-4o-mini": (0.15, 0.60),
}


class BudgetExceeded(Exception):
    pass


_current: "CostTracker | None" = None


def get_active_tracker() -> "CostTracker":
    global _current
    if _current is None:
        _current = CostTracker()
    return _current


def reset_tracker() -> CostTracker:
    global _current
    _current = CostTracker()
    return _current


class CostTracker:
    def __init__(self):
        cfg = load_yaml("models.yaml")
        self.budget = cfg.get("budget", {})
        self.session_spend = 0.0

    def estimate(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pin, pout = PRICING.get(model, (1.0, 5.0))
        return (input_tokens / 1_000_000 * pin) + (output_tokens / 1_000_000 * pout)

    def record(
        self,
        node: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        usd = self.estimate(model, input_tokens, output_tokens)
        self.session_spend += usd
        session = get_session()
        session.add(
            CostLog(
                node=node,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_usd=usd,
            )
        )
        session.commit()
        session.close()
        return usd

    def check_brief_budget(self) -> None:
        cap = float(self.budget.get("daily_brief_max_usd", 0.5))
        if self.session_spend >= cap:
            raise BudgetExceeded(
                f"Daily brief budget exceeded: ${self.session_spend:.4f} >= ${cap:.2f}"
            )

    def check_slack_budget(self) -> None:
        cap = float(self.budget.get("slack_session_max_usd", 0.05))
        if self.session_spend >= cap:
            raise BudgetExceeded(
                f"Slack session budget exceeded: ${self.session_spend:.4f} >= ${cap:.2f}"
            )


def get_model_for_node(node: str) -> dict[str, Any]:
    cfg = load_yaml("models.yaml")
    tier_name = cfg.get("node_models", {}).get(node, "l2")
    tier = dict(cfg["tiers"][tier_name])
    overrides = (cfg.get("node_overrides") or {}).get(node) or {}
    tier.update(overrides)
    return {"tier": tier_name, **tier}
