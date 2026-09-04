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

    # A job is unsuccessful if it raised, if a line marked itself failed, or if a
    # source was skipped for missing configuration.
    #
    # That last case is the one worth spelling out. The first server-side run
    # recorded ok=True while logging "GSC_SITE_URL not set — skipped" and
    # "GA4_PROPERTY_ID not set — skipped" — it had fetched nothing at all and
    # still reported success, which is the exact failure this table was built to
    # eliminate. A job that silently does nothing is not a job that worked.
    #
    # "no view events in window" is deliberately not in this list: an empty
    # window is a real, correct answer, not a misconfiguration.
    failed_markers = ("! ", "FAILED", "ERROR", "NOT READY", "not set")
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


# ── liveness ──────────────────────────────────────────────────────────────────
# Added 2026-09-03. The engine stopped publishing on 27 Aug — every remaining
# topic died at the writer on an OpenRouter error, the queue drained to empty,
# and nothing said so for seven days. `job_runs` held the evidence the whole
# time; no code ever read it back.
#
# There is no paging infrastructure here and adding one would be its own project,
# so the alarm uses what already exists: the hourly GitHub Actions cron records
# an outcome through `record()` above, and a job that reports ok=False turns that
# workflow red. Making a stalled engine *fail* its own health job is the cheapest
# true alarm available, and it needs no new service.

# A day and a half. Long enough that a 24h publish cadence plus a late tick is
# never an alert; short enough that a stall is caught the same day it happens.
STALL_HOURS = 36


def health_report(db: Any) -> list[str]:
    """Everything currently wrong with the engine, as log lines.

    Read-only and total: it never raises and never repairs. A health check that
    can itself fail is a second thing to monitor.

    Lines beginning "! " are picked up by `record()`'s failure markers, so any
    problem found here makes the enclosing job report ok=False.
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    lines = ["[health] checking engine liveness"]

    def _age_hours(value: Any) -> float | None:
        if not value:
            return None
        try:
            when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return (now - when).total_seconds() / 3600.0

    # 1. Is anything still going out?
    try:
        rows = (db.table("blog_posts").select("published_at")
                .not_.is_("published_at", "null")
                .order("published_at", desc=True).limit(1).execute().data or [])
        age = _age_hours(rows[0]["published_at"]) if rows else None
        if age is None:
            lines.append("! nothing has ever been published")
        elif age > STALL_HOURS:
            lines.append(f"! no post published in {age:.0f}h "
                         f"(threshold {STALL_HOURS}h) — the engine is stalled")
        else:
            lines.append(f"  last publish {age:.0f}h ago")
    except Exception as exc:
        lines.append(f"! could not read publish history: {exc}")

    # 2. Is there anything left to publish? An empty queue is not an error on its
    #    own — the ideator refills it — but an empty queue *and* a stalled engine
    #    means the refill is what broke, which is a different repair.
    try:
        counts: dict[str, int] = {}
        rows = db.table("topics").select("status").limit(5000).execute().data or []
        for row in rows:
            counts[row.get("status") or "?"] = counts.get(row.get("status") or "?", 0) + 1
        queued = counts.get("queued", 0) + counts.get("scheduled", 0)
        failed = counts.get("failed", 0)
        lines.append("  queue: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        if queued == 0:
            lines.append("! no queued or scheduled topics — nothing is waiting to publish")
        if failed >= 5:
            lines.append(f"! {failed} topics are in failed state — run "
                         "`python run.py --list-failed` for the reason and cost")
    except Exception as exc:
        lines.append(f"! could not read the topic queue: {exc}")

    # 3. Is the distribution lane moving? It fails more quietly than publishing:
    #    an expired LinkedIn token, a dry-run flag left on, or a cron secret with
    #    a bad URL all look exactly like "nothing was due", and the kits would go
    #    back to being written and thrown away — which is the state this whole
    #    subsystem was built to end.
    try:
        rows = db.table("distribution_queue").select("status,due_at").limit(2000).execute().data or []
    except Exception:
        rows = []          # table not migrated yet: not an error, just nothing to say
    if rows:
        queued = [r for r in rows if r.get("status") == "queued"]
        overdue = [r for r in queued
                   if (_age_hours(r.get("due_at")) or 0) > 0]
        try:
            sent = (db.table("distribution_queue").select("sent_at")
                    .eq("status", "sent").not_.is_("sent_at", "null")
                    .order("sent_at", desc=True).limit(1).execute().data or [])
        except Exception:
            sent = []
        age = _age_hours(sent[0]["sent_at"]) if sent else None
        if overdue and age is None:
            lines.append(f"! {len(overdue)} sends are overdue and nothing has EVER been "
                         "distributed — check DISTRIBUTE_DRY_RUN and DISTRIBUTE_PROVIDER")
        elif overdue and age is not None and age > STALL_HOURS * 2:
            lines.append(f"! {len(overdue)} sends overdue, last one went out {age:.0f}h ago")
        else:
            lines.append(f"  distribution: {len(queued)} queued"
                         + (f", last sent {age:.0f}h ago" if age is not None else ", none sent yet"))

    # 4. Are the background jobs themselves running and succeeding? A scout that
    #    stopped sweeping starves the ideator days before anyone sees it in the
    #    output.
    for job, max_age in (("scout", 26), ("ingest-analytics", 50), ("learn", 50)):
        try:
            rows = (db.table("job_runs").select("started_at,ok")
                    .eq("job", job).order("started_at", desc=True)
                    .limit(1).execute().data or [])
            if not rows:
                lines.append(f"! job {job!r} has never run")
                continue
            age = _age_hours(rows[0]["started_at"])
            if age is not None and age > max_age:
                lines.append(f"! job {job!r} last ran {age:.0f}h ago (expected within {max_age}h)")
            elif not rows[0].get("ok"):
                lines.append(f"! job {job!r} last run FAILED")
            else:
                lines.append(f"  job {job!r} ok, {age:.0f}h ago" if age is not None
                             else f"  job {job!r} ok")
        except Exception as exc:
            lines.append(f"! could not read job history for {job!r}: {exc}")

    if not any(line.startswith("! ") for line in lines):
        lines.append("[health] engine healthy")
    return lines
