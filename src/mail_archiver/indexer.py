from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


def _schema_path() -> Path:
    # .../mail-archiver/src/mail_archiver/indexer.py -> repo root is parents[3]
    return Path(__file__).resolve().parents[3] / "migrations" / "001_init.sql"


def init_db(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    schema = _schema_path().read_text(encoding="utf-8")
    conn.executescript(schema)
    return conn


def get_last_uid(conn: sqlite3.Connection, folder: str) -> int:
    cur = conn.execute("SELECT last_uid FROM folders WHERE name = ?", (folder,))
    row = cur.fetchone()
    return int(row[0]) if row else 0


def set_last_uid(conn: sqlite3.Connection, folder: str, last_uid: int) -> None:
    conn.execute(
        "INSERT INTO folders(name, last_uid) VALUES (?, ?) "
        "ON CONFLICT(name) DO UPDATE SET last_uid = excluded.last_uid",
        (folder, last_uid),
    )


def insert_message(
    conn: sqlite3.Connection,
    *,
    msg_id: str,
    folder: str,
    uid: int,
    message_id: str | None,
    date: str | None,
    from_addr: str | None,
    to_addr: str | None,
    subject: str | None,
    path: str,
    size: int,
    checksum: str,
    body_text: str | None,
    inserted_at: str,
) -> bool:
    cur = conn.execute(
        "INSERT OR IGNORE INTO messages "
        "(id, folder, uid, message_id, date, from_addr, to_addr, subject, path, size, checksum, inserted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            msg_id,
            folder,
            uid,
            message_id,
            date,
            from_addr,
            to_addr,
            subject,
            path,
            size,
            checksum,
            inserted_at,
        ),
    )
    if cur.rowcount == 0:
        return False

    rowid = cur.lastrowid
    conn.execute(
        "INSERT INTO messages_fts(rowid, subject, from_addr, to_addr, body_text) VALUES (?, ?, ?, ?, ?)",
        (rowid, subject or "", from_addr or "", to_addr or "", body_text or ""),
    )
    return True


def search_messages(conn: sqlite3.Connection, query: str, limit: int) -> Iterable[tuple]:
    cur = conn.execute(
        "SELECT m.date, m.from_addr, m.subject, m.path "
        "FROM messages_fts f "
        "JOIN messages m ON m.rowid = f.rowid "
        "WHERE messages_fts MATCH ? "
        "ORDER BY m.date DESC "
        "LIMIT ?",
        (query, limit),
    )
    return cur.fetchall()
