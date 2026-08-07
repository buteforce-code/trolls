"""Persisted outcomes for background CLI jobs.

The dashboard's cron endpoints spawn `run.py` and answer HTTP 200 the instant the
process starts. That is the right shape — a sweep can outlive an HTTP request —
but it means the exit status never reaches the caller. A job that dies on its
first line is indistinguishable from one that did the work, and GitHub Actions
reports green for both.

That cost real time: two scheduled runs reported success while writing nothing,
and the only way to tell was to compare row timestamps by hand and infer.

So every job writes its own log here when it finishes. One query then answers
"did last night's ingest actually work, and if not, what did it say" — including
for a process running on a host whose logs are awkward to reach.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

MAX_LOG_CHARS = 20000


def record(db: Any, job: str, lines: list[str], started_at: datetime,
           error: str | None = None) -> None:
    """Persist one job's outcome. Never raises.

    A failure to record must not turn a working job into a failed one, so this
    swallows its own errors — but prints them, so the loss is at least visible in
    whatever log the host does keep.
    """
    log = "\n".join(str(line) for line in lines)[-MAX_LOG_CHARS:]

    # A job is unsuccessful if it raised, or if any line marked itself failed.
    # The ingest deliberately continues past a broken source rather than
    # aborting, so its own log is the only place that failure is recorded.
    failed_markers = ("! ", "FAILED", "ERROR", "NOT READY")
    ok = error is None and not any(
        marker in line for line in lines for marker in failed_markers
    )

    try:
        db.table("job_runs").insert({
            "job": job,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "ok": ok,
            "log": log,
            "error": (error or "")[:2000] or None,
        }).execute()
    except Exception as exc:  # pragma: no cover - diagnostics must not cascade
        print(f"[jobs] could not record run of {job!r}: {exc}", flush=True)


def run_and_record(db: Any, job: str, fn: Any) -> list[str]:
    """Run a job that returns a log, print it, and persist the outcome."""
    started = datetime.now(timezone.utc)
    try:
        lines = fn()
    except Exception as exc:
        record(db, job, [f"CRASHED: {exc}"], started, error=str(exc))
        raise
    for line in lines:
        print(line, flush=True)
    record(db, job, lines, started)
    return lines
