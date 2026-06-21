from __future__ import annotations

import re

import markdown
from jinja2 import Template

EMAIL_TEMPLATE = Template("""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 15px;
      line-height: 1.55;
      color: #1a1a1a;
      max-width: 720px;
      margin: 0 auto;
      padding: 24px;
    }
    h1 { font-size: 1.5rem; margin: 0 0 8px; }
    h2 {
      font-size: 1.15rem;
      margin: 28px 0 10px;
      padding-bottom: 6px;
      border-bottom: 1px solid #e5e5e5;
    }
    h3 { font-size: 1rem; margin: 18px 0 8px; }
    p { margin: 0 0 12px; }
    ul, ol { margin: 0 0 12px; padding-left: 22px; }
    li { margin-bottom: 6px; }
    table {
      border-collapse: collapse;
      width: 100%;
      margin: 12px 0 18px;
      font-size: 14px;
    }
    th, td {
      border: 1px solid #d8d8d8;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }
    th { background: #f4f4f4; font-weight: 600; }
    tr:nth-child(even) td { background: #fafafa; }
    strong { font-weight: 600; }
    hr { border: none; border-top: 1px solid #e5e5e5; margin: 24px 0; }
    .subtitle { color: #666; font-size: 14px; margin-bottom: 16px; }
    .footer { font-size: 12px; color: #888; margin-top: 8px; }
  </style>
</head>
<body>
  <h1>Stock Helper Daily Brief</h1>
  <p class="subtitle">{{ subtitle }}</p>
  <div class="brief-body">{{ body_html }}</div>
  <hr>
  <p class="footer">For informational purposes only. Not investment advice.</p>
</body>
</html>
""")


def markdown_to_html(md: str) -> str:
    """Convert markdown to HTML with tables, lists, bold, etc."""
    html = markdown.markdown(
        md,
        extensions=[
            "markdown.extensions.tables",
            "markdown.extensions.fenced_code",
            "markdown.extensions.nl2br",
            "markdown.extensions.sane_lists",
        ],
        output_format="html5",
    )
    return _email_safe_tables(html)


def _email_safe_tables(html: str) -> str:
    """Add inline styles for clients that strip &lt;style&gt; in body."""
    html = html.replace("<table>", '<table style="border-collapse:collapse;width:100%;margin:12px 0;font-size:14px;">')
    html = html.replace("<th>", '<th style="border:1px solid #d8d8d8;padding:8px 10px;background:#f4f4f4;font-weight:600;text-align:left;">')
    html = html.replace("<td>", '<td style="border:1px solid #d8d8d8;padding:8px 10px;text-align:left;vertical-align:top;">')
    return html


def _escape_telegram_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline_md_to_telegram_html(text: str) -> str:
    text = _escape_telegram_html(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    return text


SECTION_EMOJI = {
    "market snapshot": "📊",
    "pre-market": "📊",
    "closing snapshot": "📊",
    "earnings": "📅",
    "macro": "🌍",
    "sector": "🏭",
    "watchlist": "📋",
    "focus": "🎯",
    "recap": "📝",
    "agent tracking": "🤖",
    "also on radar": "🤖",
    "risk": "⚠️",
}


def _section_emoji(title: str) -> str:
    lower = title.lower()
    for key, emoji in SECTION_EMOJI.items():
        if key in lower:
            return emoji
    return "•"


def _is_table_line(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 2


def _parse_table_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_table_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-+:?", c) for c in cells if c)


def _format_table_html(rows: list[list[str]]) -> str:
    if len(rows) < 2:
        return ""
    header = rows[0]
    body_rows = [r for r in rows[1:] if not _is_table_separator(r)]
    lines: list[str] = []

    if header and header[0].lower() in ("ticker", "symbol"):
        for row in body_rows:
            if len(row) >= 3:
                ticker, price, chg = row[0], row[1], row[2]
                if chg.strip().startswith("+"):
                    sign = "🟢"
                elif chg.strip().startswith("-"):
                    sign = "🔴"
                else:
                    sign = "⚪"
                lines.append(
                    f"{sign} <b>{_escape_telegram_html(ticker)}</b>  {price}  {chg}"
                )
            elif len(row) >= 2:
                lines.append(f"• <b>{_escape_telegram_html(row[0])}</b>  {row[1]}")
        return "\n".join(lines)

    for row in body_rows:
        if not row:
            continue
        if len(row) >= 2:
            lines.append(
                "• " + "  ·  ".join(_inline_md_to_telegram_html(c) for c in row)
            )
        else:
            lines.append("• " + _inline_md_to_telegram_html(row[0]))
    return "\n".join(lines)


def markdown_to_telegram_html(md: str) -> str:
    """Convert brief markdown to Telegram HTML (no raw pipe tables)."""
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            out.append("")
            i += 1
            continue

        if _is_table_line(stripped):
            table_rows: list[list[str]] = []
            while i < len(lines) and _is_table_line(lines[i].strip()):
                table_rows.append(_parse_table_row(lines[i]))
                i += 1
            formatted = _format_table_html(table_rows)
            if formatted:
                out.append(formatted)
            continue

        if stripped.startswith("# "):
            out.append(f"📈 <b>{_escape_telegram_html(stripped[2:].strip())}</b>")
            i += 1
            continue

        if stripped.startswith("## "):
            title = stripped[3:].strip()
            emoji = _section_emoji(title)
            out.append(f"\n{emoji} <b>{_inline_md_to_telegram_html(title)}</b>")
            i += 1
            continue

        if stripped.startswith("### "):
            out.append(f"\n<b>{_inline_md_to_telegram_html(stripped[4:].strip())}</b>")
            i += 1
            continue

        if stripped.startswith("- "):
            out.append("• " + _inline_md_to_telegram_html(stripped[2:]))
            i += 1
            continue

        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            out.append(f"<i>{_inline_md_to_telegram_html(stripped.strip('*'))}</i>")
            i += 1
            continue

        out.append(_inline_md_to_telegram_html(stripped))
        i += 1

    return "\n".join(out).strip()


def brief_to_telegram_messages(brief_md: str, session: str) -> list[str]:
    """Split brief into Telegram HTML messages (section-aware)."""
    html = markdown_to_telegram_html(brief_md)
    html = html.replace(
        "📈 <b>Stock Helper Daily Brief</b>",
        f"📈 <b>Stock Helper Daily Brief</b>\n<i>Session: {_escape_telegram_html(session)}</i>",
        1,
    )

    # Split on section emoji headers
    parts = re.split(r"(?=\n[📊📅🌍🏭📋🤖⚠️])", html)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return [html[:4096]]

    messages: list[str] = []
    buf = ""
    max_len = 4000
    for part in parts:
        candidate = f"{buf}\n\n{part}".strip() if buf else part
        if len(candidate) <= max_len:
            buf = candidate
        else:
            if buf:
                messages.append(buf)
            if len(part) <= max_len:
                buf = part
            else:
                messages.extend(split_text_chunks(part, max_len=max_len))
                buf = ""
    if buf:
        messages.append(buf)

    if len(messages) > 1:
        total = len(messages)
        messages = [
            (f"<i>({i + 1}/{total})</i>\n\n{m}" if i > 0 else m)
            for i, m in enumerate(messages)
        ]
    return messages


def render_email(brief_md: str, session: str) -> tuple[str, str]:
    subtitle = f"Session: {session}"
    body_html = markdown_to_html(brief_md)
    html = EMAIL_TEMPLATE.render(subtitle=subtitle, body_html=body_html)
    return brief_md, html


def split_text_chunks(text: str, max_len: int = 4000) -> list[str]:
    """Split long text for Telegram/Slack limits, preferring paragraph boundaries."""
    text = text.strip()
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n\n", 0, max_len)
        if split_at < max_len // 2:
            split_at = text.rfind("\n", 0, max_len)
        if split_at < max_len // 2:
            split_at = max_len
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()
    return [c for c in chunks if c]


def looks_truncated(brief_md: str) -> bool:
    """Heuristic: brief should end with disclaimer or complete section."""
    text = brief_md.strip()
    lower = text.lower()
    if "investment advice" in lower or "informational purposes" in lower:
        return False
    if len(text) < 200:
        return True
    if text.endswith((":", "**", "-", "|", "·")):
        return True
    if re.search(r"\*\*Catalyst:\*\*\s*$", text):
        return True
    return False
