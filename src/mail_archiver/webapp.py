from __future__ import annotations

from flask import Flask, render_template, request

from .config import load_config
from .indexer import connect_db, init_db, search_messages


def _parse_limit(value: str | None) -> int:
    try:
        limit = int(value or 50)
    except ValueError:
        return 50
    return max(1, min(limit, 200))


def create_app() -> Flask:
    config = load_config()
    init_db(config.state_db).close()

    app = Flask(__name__)

    @app.get("/")
    def index():
        query = (request.args.get("q") or "").strip()
        limit = _parse_limit(request.args.get("limit"))
        rows = []
        if query:
            conn = connect_db(config.state_db)
            try:
                rows = search_messages(conn, query, limit)
            finally:
                conn.close()
        return render_template("index.html", query=query, limit=limit, rows=rows)

    @app.get("/health")
    def health():
        return "ok"

    return app


def main() -> None:
    config = load_config()
    app = create_app()
    app.run(host=config.web_host, port=config.web_port)


if __name__ == "__main__":
    main()
