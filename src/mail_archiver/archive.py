from __future__ import annotations

from datetime import datetime, timezone
from email.message import Message
from email.utils import parsedate_to_datetime
import hashlib
from pathlib import Path
import re


def _safe_date(msg: Message) -> datetime:
    date_header = msg.get("Date")
    if date_header:
        try:
            parsed = parsedate_to_datetime(date_header)
            if parsed.tzinfo is None:
                return parsed
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
    return datetime.utcnow()


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _hash_text(data: str) -> str:
    return hashlib.sha1(data.encode("utf-8", "ignore")).hexdigest()


def build_message_id(account: str, folder: str, uid: int, message_id: str | None) -> str:
    base = f"{account}:{folder}:{uid}:{message_id or ''}"
    return _hash_text(base)


def _safe_component(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip().lower())
    return safe.strip("._-") or "account"


def archive_message(
    archive_root: str,
    account: str,
    folder: str,
    uid: int,
    raw_bytes: bytes,
    msg: Message,
) -> dict:
    msg_date = _safe_date(msg)
    date_path = Path(archive_root) / _safe_component(account) / folder / msg_date.strftime("%Y/%m/%d")
    date_path.mkdir(parents=True, exist_ok=True)

    message_id = msg.get("Message-ID")
    id_hash = _hash_text(message_id)[:12] if message_id else _hash_bytes(raw_bytes)[:12]
    filename = f"{uid}_{id_hash}.eml"
    full_path = date_path / filename

    if not full_path.exists():
        tmp_path = full_path.with_suffix(".eml.tmp")
        tmp_path.write_bytes(raw_bytes)
        tmp_path.replace(full_path)

    return {
        "path": str(full_path),
        "size": len(raw_bytes),
        "checksum": _hash_bytes(raw_bytes),
        "date": msg_date.isoformat(),
        "message_id": message_id,
    }
