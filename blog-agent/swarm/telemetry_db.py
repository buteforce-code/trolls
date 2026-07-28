"""Supabase-backed sink for swarm telemetry.

Kept separate from ``swarm/telemetry.py`` so that module stays import-clean and
directly unit-testable. Everything here is best-effort: a telemetry write must
never take down a content run, so failures print and return rather than raise.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from swarm.telemetry import RunRecorder, NullRecorder

# Rows are upserted rather than inserted so an in-progress run can be updated as
# it advances without the caller tracking whether it has been written yet.
_UPSERT_TABLES = {"agent_runs"}


def make_sink(db: Any) -> Callable[[str, dict[str, Any]], None]:
    """Build a sink that writes telemetry rows to Supabase."""
    def sink(table: str, row: dict[str, Any]) -> None:
        if table in _UPSERT_TABLES:
            db.table(table).upsert(row, on_conflict="id").execute()
        else:
            db.table(table).insert(row).execute()
    return sink


def spend_today_usd(db: Any) -> float:
    """Total estimated USD across all runs started in the last 24 hours.

    Feeds the daily ceiling. Returns 0.0 if the table is missing or unreadable —
    a telemetry outage should not be able to halt publishing.
    """
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    try:
        res = (
            db.table("agent_runs")
            .select("total_cost_usd")
            .gte("started_at", since)
            .execute()
        )
    except Exception as exc:
        print(f"[swarm] could not read daily spend (ceiling not enforced): {exc}", flush=True)
        return 0.0
    total = 0.0
    for row in res.data or []:
        try:
            total += float(row.get("total_cost_usd") or 0)
        except (TypeError, ValueError):
            continue
    return round(total, 6)


def make_recorder(
    db: Any,
    topic_slug: str,
    topic_id: str | None = None,
    trigger: str = "manual",
) -> RunRecorder:
    """Recorder wired to Supabase, or a NullRecorder if telemetry is disabled.

    Set ``SWARM_TELEMETRY=false`` to turn recording off entirely (the pipeline
    still runs; it just goes back to being invisible).
    """
    if os.environ.get("SWARM_TELEMETRY", "true").strip().lower() == "false":
        return NullRecorder()
    try:
        return RunRecorder(
            topic_slug=topic_slug,
            topic_id=topic_id,
            trigger=trigger,
            sink=make_sink(db),
            prior_day_cost_usd=spend_today_usd(db),
        )
    except Exception as exc:
        print(f"[swarm] telemetry unavailable, continuing without it: {exc}", flush=True)
        return NullRecorder()
