from __future__ import annotations

from dataclasses import dataclass
import os


def _getenv_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _getenv_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    imap_host: str
    imap_port: int
    imap_users: list[str]
    imap_passwords: list[str]
    imap_accounts: list[tuple[str, str]]
    imap_ssl: bool
    imap_folders: list[str]
    archive_root: str
    state_db: str
    log_path: str | None
    metrics_pushgateway_url: str | None
    metrics_job: str
    metrics_instance: str | None
    metrics_textfile: str | None
    metrics_top_senders: int
    metrics_top_domains: int
    web_host: str
    web_port: int


def _getenv_list(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def load_config() -> Config:
    folders = os.getenv("IMAP_FOLDERS", "INBOX,Sent,Junk")
    folder_list = [f.strip() for f in folders.split(",") if f.strip()]
    users = _getenv_list("IMAP_USER")
    passwords = _getenv_list("IMAP_PASSWORD")

    if not users or not passwords or len(users) != len(passwords):
        raise ValueError("IMAP_USER and IMAP_PASSWORD must be set and have the same number of entries")

    return Config(
        imap_host=os.getenv("IMAP_HOST", "imap.web.de"),
        imap_port=_getenv_int("IMAP_PORT", 993),
        imap_users=users,
        imap_passwords=passwords,
        imap_accounts=list(zip(users, passwords)),
        imap_ssl=_getenv_bool("IMAP_SSL", True),
        imap_folders=folder_list,
        archive_root=os.getenv("ARCHIVE_ROOT", "/data"),
        state_db=os.getenv("STATE_DB", "/data/index/mail.db"),
        log_path=os.getenv("LOG_PATH") or None,
        metrics_pushgateway_url=os.getenv("METRICS_PUSHGATEWAY_URL") or None,
        metrics_job=os.getenv("METRICS_JOB", "mail_archiver"),
        metrics_instance=os.getenv("METRICS_INSTANCE") or None,
        metrics_textfile=os.getenv("METRICS_TEXTFILE") or None,
        metrics_top_senders=_getenv_int("METRICS_TOP_SENDERS", 10),
        metrics_top_domains=_getenv_int("METRICS_TOP_DOMAINS", 10),
        web_host=os.getenv("WEB_HOST", "0.0.0.0"),
        web_port=_getenv_int("WEB_PORT", 8080),
    )
