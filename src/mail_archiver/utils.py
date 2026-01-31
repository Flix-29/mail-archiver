from __future__ import annotations

from datetime import datetime, timezone
from email.message import Message
import logging
import re

from bs4 import BeautifulSoup


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def extract_body_text(msg: Message) -> str:
    if msg.is_multipart():
        parts = msg.walk()
    else:
        parts = [msg]

    plain_parts = []
    html_parts = []

    for part in parts:
        content_type = part.get_content_type()
        if content_type == "text/plain":
            text = _get_part_text(part)
            if text:
                plain_parts.append(text)
        elif content_type == "text/html":
            text = _get_part_text(part)
            if text:
                html_parts.append(text)

    if plain_parts:
        return "\n".join(p.strip() for p in plain_parts if p)

    if html_parts:
        return _strip_html("\n".join(h for h in html_parts if h))

    return ""


def _get_part_text(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        payload = None

    if payload is None:
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""

    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _strip_html(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text("\n", strip=True)
    except Exception:
        # Fallback: very rough tag removal
        return re.sub(r"<[^>]+>", " ", html)
