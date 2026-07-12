from __future__ import annotations

from typing import Any


def build_beginner_storyline(snapshot: dict[str, Any]) -> str:
    """Plain-language 30-second market story for beginners."""
    regime = snapshot.get("regime") or {}
    dims = regime.get("dimension_labels") or {}
    structure = snapshot.get("structure") or {}
    sentiment = snapshot.get("sentiment") or {}
    breadth = structure.get("breadth") or {}

    inflation = dims.get("inflation", "?")
    growth = dims.get("growth", "?")
    policy = dims.get("policy", "?")
    risk = dims.get("risk", "?")
    composite = regime.get("regime", "mixed").replace("_", " ")

    breadth_line = breadth.get("interpretation", "")
    mood = sentiment.get("mood", "neutral")

    lines = [
        "## In 30 seconds",
        "",
        f"Think of the market like weather: right now it's **{composite}** — "
        f"inflation is **{inflation}**, growth is **{growth}**, "
        f"the Fed stance looks **{policy}**, and fear gauge risk is **{risk}**.",
        "",
    ]

    if breadth.get("signal") == "narrow_rally":
        lines.append(
            "The headline index can look green while only a few huge stocks do the heavy lifting — "
            "like a team winning because one star player scored all the points."
        )
    elif breadth.get("signal") == "broad_participation":
        lines.append(
            "More stocks are participating in the move — a healthier sign, "
            "like a balanced team effort."
        )
    else:
        lines.append(
            "Market breadth is mixed today — don't read too much into one session."
        )

    lines.append("")
    lines.append(
        f"News mood feels **{mood}** over the past couple of weeks. "
        "Check voice/topic sections below for who is moving the conversation."
    )
    lines.append("")
    lines.append("**So what for a beginner?**")
    lines.append("- Focus on why indices move (macro + breadth), not just daily red/green.")
    if growth in ("slowing", "weak", "soft") and policy in ("tight", "neutral_tight", "restrictive"):
        lines.append(
            "- Growth is slowing and policy is tight — growth indices (QQQ) often feel more pressure."
        )
    elif growth in ("firm", "strong", "solid"):
        lines.append(
            "- Growth is still firm — leadership can stay in quality and mega-cap tech when breadth is narrow."
        )
    else:
        lines.append(
            "- Mixed growth/policy readings — compare QQQ vs SPY and RSP vs SPY before chasing headlines."
        )
    lines.append("- Use L1/L2/L3 sections as templates, not buy/sell orders.")
    return "\n".join(lines)
