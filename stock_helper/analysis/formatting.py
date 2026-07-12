from __future__ import annotations


def fmt_num(value, digits: int = 1) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return str(round(value, digits))
    return str(value)


def note(text: str) -> str:
    """Secondary line for reports (no markdown underscores)."""
    if not text:
        return ""
    return f"Note: {text}"


def support_line(items: str, confidence: float | None = None) -> str:
    parts = [f"Support: {items}"]
    if confidence is not None:
        parts.append(f"confidence {fmt_num(confidence, 2)}")
    return "  (" + " · ".join(parts) + ")"
