from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterable, Mapping
from urllib.parse import quote
from urllib.request import Request, urlopen


Metric = tuple[str, Mapping[str, str] | None, float | int]


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _format_labels(labels: Mapping[str, str] | None) -> str:
    if not labels:
        return ""
    parts = [f'{k}="{_escape_label_value(v)}"' for k, v in labels.items()]
    return "{" + ",".join(parts) + "}"


def _render_metrics(metrics: Iterable[Metric]) -> str:
    lines = []
    for name, labels, value in metrics:
        lines.append(f"{name}{_format_labels(labels)} {value}")
    return "\n".join(lines) + "\n"


def write_textfile(path: str, metrics: Iterable[Metric]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(_render_metrics(metrics), encoding="utf-8")
    tmp.replace(target)


def push_to_gateway(url: str, job: str, instance: str | None, metrics: Iterable[Metric]) -> None:
    safe_job = quote(job, safe="")
    if instance:
        safe_instance = quote(instance, safe="")
        push_url = f"{url.rstrip('/')}/metrics/job/{safe_job}/instance/{safe_instance}"
    else:
        push_url = f"{url.rstrip('/')}/metrics/job/{safe_job}"

    data = _render_metrics(metrics).encode("utf-8")
    req = Request(push_url, data=data, method="PUT")
    req.add_header("Content-Type", "text/plain")
    with urlopen(req, timeout=10) as _:
        pass


def build_run_metrics(
    *,
    archived: int,
    errors: int,
    duration_seconds: float,
    success: bool,
) -> list[Metric]:
    now = int(time.time())
    metrics: list[Metric] = [
        ("mail_archiver_last_run_timestamp", None, now),
        ("mail_archiver_run_duration_seconds", None, round(duration_seconds, 3)),
        ("mail_archiver_messages_archived", None, archived),
        ("mail_archiver_errors", None, errors),
        ("mail_archiver_success", None, 1 if success else 0),
    ]
    if success:
        metrics.append(("mail_archiver_last_success_timestamp", None, now))
    return metrics


def build_db_metrics(
    *,
    total_messages: int,
    total_bytes: int,
    unique_senders: int,
    top_senders: Iterable[tuple[str, int]],
) -> list[Metric]:
    metrics: list[Metric] = [
        ("mail_archiver_total_messages", None, total_messages),
        ("mail_archiver_total_bytes", None, total_bytes),
        ("mail_archiver_unique_senders", None, unique_senders),
    ]
    for sender, count in top_senders:
        metrics.append(("mail_archiver_sender_total", {"sender": sender}, count))
    return metrics


def default_instance() -> str | None:
    try:
        return os.uname().nodename
    except Exception:
        return None
