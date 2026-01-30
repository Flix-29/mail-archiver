from __future__ import annotations

import imaplib
import logging
from email import policy
from email.message import Message
from email.parser import BytesParser
from typing import Iterable

from .archive import archive_message, build_message_id
from .indexer import get_last_uid, insert_message, set_last_uid
from .utils import extract_body_text, now_utc_iso


def _parse_message(raw_bytes: bytes) -> Message:
    return BytesParser(policy=policy.default).parsebytes(raw_bytes)


def _iter_uids(data: list[bytes]) -> Iterable[int]:
    if not data or not data[0]:
        return []
    return [int(uid) for uid in data[0].split()]


def sync_folder(
    imap: imaplib.IMAP4,
    *,
    folder: str,
    conn,
    archive_root: str,
    max_messages: int | None = None,
) -> int:
    typ, _ = imap.select(folder, readonly=True)
    if typ != "OK":
        logging.warning("Skipping folder %s (select failed)", folder)
        return 0

    last_uid = get_last_uid(conn, folder)
    start_uid = last_uid + 1
    typ, data = imap.uid("SEARCH", None, f"UID {start_uid}:*")
    if typ != "OK":
        logging.warning("UID search failed for %s", folder)
        return 0

    uids = list(_iter_uids(data))
    if not uids:
        return 0

    count = 0
    for uid in uids:
        if max_messages and count >= max_messages:
            break

        typ, msg_data = imap.uid("FETCH", str(uid), "(RFC822)")
        if typ != "OK" or not msg_data:
            logging.warning("Fetch failed for %s UID %s", folder, uid)
            continue

        raw_bytes = None
        for item in msg_data:
            if isinstance(item, tuple) and item[1]:
                raw_bytes = item[1]
                break

        if not raw_bytes:
            logging.warning("Empty message for %s UID %s", folder, uid)
            continue

        msg = _parse_message(raw_bytes)
        archive_info = archive_message(archive_root, folder, uid, raw_bytes, msg)
        body_text = extract_body_text(msg)
        msg_id = build_message_id(folder, uid, archive_info.get("message_id"))

        inserted = insert_message(
            conn,
            msg_id=msg_id,
            folder=folder,
            uid=uid,
            message_id=archive_info.get("message_id"),
            date=archive_info.get("date"),
            from_addr=str(msg.get("From", "")),
            to_addr=str(msg.get("To", "")),
            subject=str(msg.get("Subject", "")),
            path=archive_info.get("path"),
            size=int(archive_info.get("size", 0)),
            checksum=str(archive_info.get("checksum", "")),
            body_text=body_text,
            inserted_at=now_utc_iso(),
        )

        if inserted:
            count += 1

        set_last_uid(conn, folder, uid)
        conn.commit()

    return count


def connect_imap(host: str, port: int, ssl: bool) -> imaplib.IMAP4:
    if ssl:
        return imaplib.IMAP4_SSL(host, port)
    return imaplib.IMAP4(host, port)
