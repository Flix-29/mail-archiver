from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import load_config
from .imap_sync import connect_imap, sync_folder
from .indexer import init_db, search_messages


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
    config = load_config()
    _setup_logging(config.log_path)

    if not config.imap_user or not config.imap_password:
        logging.error("IMAP_USER or IMAP_PASSWORD not set")
        return 2

    conn = init_db(config.state_db)
    try:
        imap = connect_imap(config.imap_host, config.imap_port, config.imap_ssl)
        imap.login(config.imap_user, config.imap_password)
    except Exception as exc:
        logging.error("IMAP connection failed: %s", exc)
        return 2

    total = 0
    try:
        for folder in config.imap_folders:
            count = sync_folder(
                imap,
                folder=folder,
                conn=conn,
                archive_root=config.archive_root,
                max_messages=args.max_messages,
            )
            logging.info("%s: %s messages archived", folder, count)
            total += count
    finally:
        try:
            imap.logout()
        except Exception:
            pass
        conn.close()

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

    for date, from_addr, subject, path in rows:
        print(f"{date}\t{from_addr}\t{subject}\t{path}")

    return 0


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

    return parser


def main() -> int:
    load_dotenv("config/.env", override=False)
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
