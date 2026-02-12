from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from .config import load_config
from .imap_sync import connect_imap, sync_folder
from .indexer import get_top_senders, get_top_domains, get_totals, init_db, migrate_legacy_state, search_messages
from .metrics import (
    build_db_metrics,
    build_run_metrics,
    default_instance,
    push_to_gateway,
    write_textfile,
)
from .webapp import create_app


def _setup_logging(log_path: str | None) -> None:
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_path:
        log_dir = str(Path(log_path).parent)
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def cmd_sync(args: argparse.Namespace) -> int:
    try:
        config = load_config()
    except ValueError as exc:
        _setup_logging(None)
        logging.error("%s", exc)
        return 2
    _setup_logging(config.log_path)

    start = time.time()
    total = 0
    errors = 0
    success = False

    conn = init_db(config.state_db)
    migrate_legacy_state(conn, config.imap_accounts[0][0])
    conn.commit()

    total_messages = 0
    total_bytes = 0
    unique_senders = 0
    top_senders: list[tuple[str, int]] = []
    top_domains: list[tuple[str, int]] = []
    try:
        for user, password in config.imap_accounts:
            try:
                imap = connect_imap(config.imap_host, config.imap_port, config.imap_ssl)
                imap.login(user, password)
            except Exception as exc:
                logging.error("IMAP connection failed for %s: %s", user, exc)
                errors += 1
                continue

            try:
                for folder in config.imap_folders:
                    count, folder_errors = sync_folder(
                        imap,
                        account=user,
                        folder=folder,
                        conn=conn,
                        archive_root=config.archive_root,
                        max_messages=args.max_messages,
                    )
                    errors += folder_errors
                    logging.info("%s [%s]: %s messages archived", folder, user, count)
                    total += count
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass

        total_messages, total_bytes, unique_senders = get_totals(conn)
        if config.metrics_top_senders > 0:
            top_senders = get_top_senders(conn, config.metrics_top_senders)
        if config.metrics_top_domains > 0:
            top_domains = get_top_domains(conn, config.metrics_top_domains)
    finally:
        conn.close()

    success = errors == 0
    _emit_metrics(
        config,
        total,
        errors,
        start,
        success,
        (total_messages, total_bytes, unique_senders),
        top_senders,
        top_domains,
    )

    logging.info("Done. Total archived: %s", total)
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    config = load_config()
    _setup_logging(config.log_path)

    conn = init_db(config.state_db)
    try:
        rows = search_messages(conn, args.query, args.limit)
    finally:
        conn.close()

    for _, date, from_addr, subject, path in rows:
        print(f"{date}\t{from_addr}\t{subject}\t{path}")

    return 0


def cmd_web(args: argparse.Namespace) -> int:
    config = load_config()
    _setup_logging(config.log_path)
    app = create_app()
    app.run(host=config.web_host, port=config.web_port)
    return 0


def _emit_metrics(
    config,
    total: int,
    errors: int,
    start: float,
    success: bool,
    totals: tuple[int, int, int] | None,
    top_senders: list[tuple[str, int]] | None,
    top_domains: list[tuple[str, int]] | None,
) -> None:
    if not config.metrics_pushgateway_url and not config.metrics_textfile:
        return

    duration = time.time() - start
    metrics = build_run_metrics(
        archived=total,
        errors=errors,
        duration_seconds=duration,
        success=success,
    )

    if totals:
        total_messages, total_bytes, unique_senders = totals
        metrics.extend(
            build_db_metrics(
                total_messages=total_messages,
                total_bytes=total_bytes,
                unique_senders=unique_senders,
                top_senders=top_senders or [],
                top_domains=top_domains or [],
            )
        )

    instance = config.metrics_instance or default_instance()
    if config.metrics_textfile:
        write_textfile(config.metrics_textfile, metrics)
    if config.metrics_pushgateway_url:
        push_to_gateway(config.metrics_pushgateway_url, config.metrics_job, instance, metrics)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archive-mail")
    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync", help="Fetch new mail and update archive")
    sync.add_argument("--max-messages", type=int, default=None, help="Limit messages per run")
    sync.set_defaults(func=cmd_sync)

    search = sub.add_parser("search", help="Search the archive")
    search.add_argument("query", help="FTS query string")
    search.add_argument("--limit", type=int, default=20, help="Max results")
    search.set_defaults(func=cmd_search)

    web = sub.add_parser("web", help="Run the web UI")
    web.set_defaults(func=cmd_web)

    return parser


def main() -> int:
    load_dotenv("config/.env", override=False)
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
