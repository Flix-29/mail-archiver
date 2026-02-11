from __future__ import annotations

from pathlib import Path
import re
import sqlite3

from flask import Flask, abort, render_template, request, send_file

from .config import load_config
from .indexer import (
    connect_db,
    count_messages,
    get_message_by_rowid,
    init_db,
    search_messages,
)


def _parse_limit(value: str | None) -> int:
    try:
        limit = int(value or 50)
    except ValueError:
        return 50
    return max(1, min(limit, 200))


def _parse_page(value: str | None) -> int:
    try:
        page = int(value or 1)
    except ValueError:
        return 1
    return max(1, page)


def _parse_sort(value: str | None) -> str:
    if value in {"date_asc", "date_desc", "from_asc", "subject_asc"}:
        return value
    return "date_desc"


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _escape_fts_query(query: str) -> str:
    terms = [t for t in re.split(r"\s+", query.strip()) if t]
    if not terms:
        return ""
    escaped_terms = []
    for term in terms:
        safe = term.replace('"', '""')
        escaped_terms.append(f'"{safe}"')
    return " AND ".join(escaped_terms)


def create_app() -> Flask:
    config = load_config()
    init_db(config.state_db).close()
    archive_root = Path(config.archive_root).resolve()
    folders = config.imap_folders

    app = Flask(__name__)

    @app.get("/")
    def index():
        query = (request.args.get("q") or "").strip()
        raw = _parse_bool(request.args.get("raw"), default=True)
        limit = _parse_limit(request.args.get("limit"))
        page = _parse_page(request.args.get("page"))
        sort = _parse_sort(request.args.get("sort"))
        offset = (page - 1) * limit

        total = 0
        rows = []
        error = ""
        if query:
            conn = connect_db(config.state_db)
            try:
                fts_query = query if raw else _escape_fts_query(query)
                total = count_messages(conn, fts_query)
                rows = search_messages(conn, fts_query, limit, offset=offset, sort=sort)
            except sqlite3.OperationalError as exc:
                error = str(exc)
            finally:
                conn.close()
        total_pages = max(1, (total + limit - 1) // limit) if query else 1
        return render_template(
            "index.html",
            query=query,
            raw=raw,
            limit=limit,
            page=page,
            sort=sort,
            total=total,
            total_pages=total_pages,
            rows=rows,
            error=error,
        )

    @app.get("/view/<int:rowid>")
    def view_message(rowid: int):
        conn = connect_db(config.state_db)
        try:
            row = get_message_by_rowid(conn, rowid)
        finally:
            conn.close()
        if not row:
            abort(404)
        _, _, _, path = row
        resolved = _resolve_message_path(path, archive_root, folders)
        if not resolved:
            abort(404)
        return send_file(resolved, mimetype="message/rfc822", as_attachment=False)

    @app.get("/download/<int:rowid>")
    def download_message(rowid: int):
        conn = connect_db(config.state_db)
        try:
            row = get_message_by_rowid(conn, rowid)
        finally:
            conn.close()
        if not row:
            abort(404)
        _, _, _, path = row
        resolved = _resolve_message_path(path, archive_root, folders)
        if not resolved:
            abort(404)
        return send_file(resolved, as_attachment=True, download_name=resolved.name)

    @app.get("/health")
    def health():
        return "ok"

    return app


def _is_safe_path(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_message_path(stored_path: str, archive_root: Path, folders: list[str]) -> Path | None:
    raw_path = Path(stored_path)

    if not raw_path.is_absolute():
        candidate = (archive_root / raw_path).resolve()
        if _is_safe_path(candidate, archive_root) and candidate.exists():
            return candidate
        return None

    resolved = raw_path.resolve()
    if _is_safe_path(resolved, archive_root) and resolved.exists():
        return resolved

    parts = raw_path.parts
    for folder in folders:
        if folder in parts:
            idx = parts.index(folder)
            rel = Path(*parts[idx:])
            candidate = (archive_root / rel).resolve()
            if _is_safe_path(candidate, archive_root) and candidate.exists():
                return candidate

    return None


def main() -> None:
    config = load_config()
    app = create_app()
    app.run(host=config.web_host, port=config.web_port)


if __name__ == "__main__":
    main()
