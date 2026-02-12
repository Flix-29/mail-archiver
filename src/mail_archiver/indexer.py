from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


def _schema_path() -> Path:
    # .../mail-archiver/src/mail_archiver/indexer.py -> repo root is parents[2] (/app)
    return Path(__file__).resolve().parents[2] / "migrations" / "001_init.sql"


def init_db(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA journal_mode = DELETE")
    schema = _schema_path().read_text(encoding="utf-8")
    conn.executescript(schema)
    _ensure_schema(conn)
    return conn


def connect_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, name: str, definition: str) -> None:
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    except sqlite3.OperationalError:
        pass


def _ensure_schema(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "messages", "from_email", "TEXT")
    _ensure_column(conn, "messages", "account", "TEXT")
    conn.execute("UPDATE messages SET account = '' WHERE account IS NULL")

    conn.execute(
        "CREATE TABLE IF NOT EXISTS folder_state ("
        "account TEXT NOT NULL, "
        "name TEXT NOT NULL, "
        "last_uid INTEGER NOT NULL, "
        "PRIMARY KEY(account, name)"
        ")"
    )

    # Drop legacy uniqueness and enforce account-scoped UID uniqueness.
    conn.execute("DROP INDEX IF EXISTS idx_messages_folder_uid")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_account_folder_uid "
        "ON messages(account, folder, uid)"
    )


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,))
    return cur.fetchone() is not None


def get_last_uid(conn: sqlite3.Connection, account: str, folder: str) -> int:
    cur = conn.execute(
        "SELECT last_uid FROM folder_state WHERE account = ? AND name = ?",
        (account, folder),
    )
    row = cur.fetchone()
    return int(row[0]) if row else 0


def set_last_uid(conn: sqlite3.Connection, account: str, folder: str, last_uid: int) -> None:
    conn.execute(
        "INSERT INTO folder_state(account, name, last_uid) VALUES (?, ?, ?) "
        "ON CONFLICT(account, name) DO UPDATE SET last_uid = excluded.last_uid",
        (account, folder, last_uid),
    )


def migrate_legacy_state(conn: sqlite3.Connection, account: str) -> None:
    if not _table_exists(conn, "folders"):
        return

    conn.execute(
        "INSERT INTO folder_state(account, name, last_uid) "
        "SELECT ?, f.name, f.last_uid FROM folders f "
        "WHERE NOT EXISTS ("
        "  SELECT 1 FROM folder_state s WHERE s.account = ? AND s.name = f.name"
        ")",
        (account, account),
    )

    conn.execute(
        "UPDATE messages SET account = ? "
        "WHERE account IS NULL OR account = ''",
        (account,),
    )


def insert_message(
    conn: sqlite3.Connection,
    *,
    msg_id: str,
    account: str,
    folder: str,
    uid: int,
    message_id: str | None,
    date: str | None,
    from_addr: str | None,
    from_email: str | None,
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
        "(id, account, folder, uid, message_id, date, from_addr, from_email, to_addr, subject, path, size, checksum, inserted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            msg_id,
            account,
            folder,
            uid,
            message_id,
            date,
            from_addr,
            from_email,
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


def _order_by(sort: str) -> str:
    if sort == "date_asc":
        return "m.date ASC"
    if sort == "from_asc":
        return "m.from_addr ASC"
    if sort == "subject_asc":
        return "m.subject ASC"
    return "m.date DESC"


def count_messages(conn: sqlite3.Connection, query: str) -> int:
    cur = conn.execute(
        "SELECT COUNT(*) "
        "FROM messages_fts f "
        "JOIN messages m ON m.rowid = f.rowid "
        "WHERE messages_fts MATCH ?",
        (query,),
    )
    row = cur.fetchone() or (0,)
    return int(row[0])


def search_messages(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    offset: int = 0,
    sort: str = "date_desc",
) -> Iterable[tuple]:
    order_by = _order_by(sort)
    cur = conn.execute(
        "SELECT m.rowid, m.date, m.from_addr, m.subject, m.path "
        "FROM messages_fts f "
        "JOIN messages m ON m.rowid = f.rowid "
        "WHERE messages_fts MATCH ? "
        f"ORDER BY {order_by} "
        "LIMIT ? OFFSET ?",
        (query, limit, offset),
    )
    return cur.fetchall()


def get_message_by_rowid(conn: sqlite3.Connection, rowid: int) -> tuple | None:
    cur = conn.execute(
        "SELECT m.date, m.from_addr, m.subject, m.path "
        "FROM messages m WHERE m.rowid = ?",
        (rowid,),
    )
    return cur.fetchone()


def get_totals(conn: sqlite3.Connection) -> tuple[int, int, int]:
    cur = conn.execute("SELECT COUNT(*), COALESCE(SUM(size), 0) FROM messages")
    row = cur.fetchone() or (0, 0)
    total_messages = int(row[0])
    total_bytes = int(row[1])

    cur = conn.execute(
        "SELECT COUNT(DISTINCT COALESCE(NULLIF(from_email, ''), from_addr)) "
        "FROM messages WHERE (from_email IS NOT NULL AND from_email != '') "
        "OR (from_addr IS NOT NULL AND from_addr != '')"
    )
    row = cur.fetchone() or (0,)
    unique_senders = int(row[0])

    return total_messages, total_bytes, unique_senders


def get_top_domains(conn: sqlite3.Connection, limit: int) -> list[tuple[str, int]]:
    if limit <= 0:
        return []
    cur = conn.execute(
        "SELECT SUBSTR(from_email, INSTR(from_email, '@') + 1) AS domain, COUNT(*) AS c "
        "FROM messages WHERE from_email IS NOT NULL AND from_email != '' "
        "GROUP BY domain ORDER BY c DESC LIMIT ?",
        (limit,),
    )
    return [(row[0], int(row[1])) for row in cur.fetchall() if row[0]]


def get_top_senders(conn: sqlite3.Connection, limit: int) -> list[tuple[str, int]]:
    if limit <= 0:
        return []
    cur = conn.execute(
        "SELECT COALESCE(NULLIF(from_email, ''), from_addr) AS sender, COUNT(*) AS c "
        "FROM messages WHERE (from_email IS NOT NULL AND from_email != '') "
        "OR (from_addr IS NOT NULL AND from_addr != '') "
        "GROUP BY sender ORDER BY c DESC LIMIT ?",
        (limit,),
    )
    return [(row[0], int(row[1])) for row in cur.fetchall() if row[0]]
