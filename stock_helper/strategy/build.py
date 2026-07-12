from __future__ import annotations

from typing import Any

from stock_helper.cio.pipeline import build_cio_pipeline
from stock_helper.cio.report import format_cio_pipeline

__all__ = ["build_cio_strategy", "format_cio_markdown"]


def build_cio_strategy(
    snapshot: dict[str, Any],
    *,
    risk_level: str | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Backward-compatible entry — delegates to CIO pipeline v2."""
    return build_cio_pipeline(snapshot, risk_level=risk_level, refresh=refresh)


def format_cio_markdown(strategy: dict[str, Any], *, lang: str | None = None) -> str:
    return format_cio_pipeline(strategy, lang=lang)
