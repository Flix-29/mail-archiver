from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Mapping
from urllib.parse import quote
from urllib.request import Request, urlopen


MetricMap = Mapping[str, float | int]


def _render_metrics(metrics: MetricMap) -> str:
    lines = []
    for name, value in metrics.items():
        lines.append(f"{name} {value}")
    return "\n".join(lines) + "\n"


def write_textfile(path: str, metrics: MetricMap) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(_render_metrics(metrics), encoding="utf-8")
    tmp.replace(target)


def push_to_gateway(url: str, job: str, instance: str | None, metrics: MetricMap) -> None:
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
) -> MetricMap:
    now = int(time.time())
    metrics: dict[str, float | int] = {
        "mail_archiver_last_run_timestamp": now,
        "mail_archiver_run_duration_seconds": round(duration_seconds, 3),
        "mail_archiver_messages_archived": archived,
        "mail_archiver_errors": errors,
        "mail_archiver_success": 1 if success else 0,
    }
    if success:
        metrics["mail_archiver_last_success_timestamp"] = now
    return metrics


def default_instance() -> str | None:
    try:
        return os.uname().nodename
    except Exception:
        return None
