from __future__ import annotations

import httpx

from stock_helper.config import get_settings
from stock_helper.outputs.brief_renderer import render_email


def send_brief_email(brief_md: str, session: str) -> bool:
    settings = get_settings()
    if not settings.resend_api_key or not settings.email_to:
        return False

    subject = f"Stock Helper Brief — {session}"
    _, html = render_email(brief_md, session)

    payload = {
        "from": settings.email_from,
        "to": [settings.email_to],
        "subject": subject,
        "html": html,
        "text": brief_md,
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
    return True
