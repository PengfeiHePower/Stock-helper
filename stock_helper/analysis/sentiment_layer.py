from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from stock_helper.collectors.ingest import load_recent_news
from stock_helper.config import load_yaml


def _voices_cfg() -> dict[str, Any]:
    return load_yaml("voices.yaml")


def analyze_sentiment_layer(days: int | None = None) -> dict[str, Any]:
    cfg = _voices_cfg()
    if not cfg.get("enabled", True):
        return {"enabled": False}

    lookback = days or int(cfg.get("lookback_days", 14))
    news = load_recent_news(limit=200)
    cutoff = datetime.utcnow() - timedelta(days=lookback)

    recent = []
    for item in news:
        pub = item.get("published_at")
        if pub and pub.replace(tzinfo=None) < cutoff:
            continue
        recent.append(item)

    voice_hits: dict[str, list[dict]] = {v["id"]: [] for v in cfg.get("voices") or []}
    topic_counts: Counter[str] = Counter()

    for item in recent:
        text = f"{item.get('headline', '')} {item.get('summary', '')}".lower()
        for voice in cfg.get("voices") or []:
            if any(kw.lower() in text for kw in voice.get("keywords") or []):
                voice_hits[voice["id"]].append(
                    {
                        "headline": item.get("headline"),
                        "tickers": item.get("tickers"),
                        "event_type": item.get("event_type"),
                    }
                )
        for topic, keywords in (cfg.get("topic_keywords") or {}).items():
            if any(kw.lower() in text for kw in keywords):
                topic_counts[topic] += 1

    top_topics = topic_counts.most_common(6)
    mood = _overall_mood(top_topics, len(recent))

    voice_summary = []
    for voice in cfg.get("voices") or []:
        hits = voice_hits.get(voice["id"]) or []
        voice_summary.append(
            {
                "id": voice["id"],
                "name": voice["name"],
                "name_zh": voice.get("name_zh"),
                "mention_count": len(hits),
                "sample_headlines": [h["headline"] for h in hits[:3]],
            }
        )

    return {
        "enabled": True,
        "lookback_days": lookback,
        "news_count": len(recent),
        "mood": mood,
        "top_topics": [{"topic": t, "count": c} for t, c in top_topics],
        "voices": voice_summary,
    }


def _overall_mood(top_topics: list[tuple[str, int]], news_count: int) -> str:
    if news_count == 0:
        return "quiet"
    topic_map = dict(top_topics)
    if topic_map.get("tariff", 0) >= 3 or topic_map.get("rates", 0) >= 4:
        return "cautious"
    if topic_map.get("ai", 0) >= 3:
        return "optimistic_thematic"
    return "neutral"


def format_sentiment_markdown(sentiment: dict[str, Any]) -> str:
    if not sentiment.get("enabled"):
        return "Sentiment layer disabled."

    lines = [
        f"**Mood (news, {sentiment.get('lookback_days')}d):** {sentiment.get('mood')}",
        f"**Headlines scanned:** {sentiment.get('news_count')}",
        "",
        "**Hot topics:**",
    ]
    for t in sentiment.get("top_topics") or []:
        lines.append(f"- {t['topic']}: {t['count']} mentions")

    lines.append("")
    lines.append("**Voices tracked:**")
    for v in sentiment.get("voices") or []:
        if v["mention_count"] == 0:
            continue
        lines.append(f"- **{v['name']}** ({v['mention_count']} headlines)")
        for h in v.get("sample_headlines") or []:
            lines.append(f"  - {h[:120]}")

    if not any(v["mention_count"] for v in sentiment.get("voices") or []):
        lines.append("No voice-specific headlines in this window.")

    return "\n".join(lines)
