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
