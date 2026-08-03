"""
Autopilot — the autonomous engine.

One idempotent `run_tick()`:
  1. Publish any 'scheduled' post whose scheduled_for has arrived (at most one per
     tick; re-space the rest so a backlog after downtime never dumps all at once).
  2. Keep AUTOPILOT_BUFFER finished posts scheduled ahead — research + write the next
     queued topic, then move it to 'scheduled' at the next free slot (24h veto window).
  3. When the queue is empty, run the ideator to generate fresh topics across every vertical.

Cadence is enforced by per-post `scheduled_for` timestamps, so the tick can fire on a
coarse schedule (hourly is plenty). Designed to be triggered by GitHub Actions hitting
the dashboard's secret-protected /api/autopilot/tick, which spawns `run.py --autopilot`.

Env knobs (all optional, with sane defaults):
  AUTOPILOT_ENABLED              "true" | "false"  (kill switch)         default true
  PUBLISH_GAP_HOURS              hours between published posts            default 24
  AUTOPILOT_BUFFER              finished posts to keep scheduled ahead    default 1
  AUTOPILOT_IDEATE_BATCH        topics to generate when the queue empties default 8
  AUTOPILOT_MAX_PRODUCE_PER_TICK cap on research+write work per tick      default 1
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from swarm.slugs import slugify
from swarm.telemetry import SpendCeilingExceeded

# A topic in one of these states means a tick is (or was) actively working it.
ACTIVE_STATES = ("researching", "writing", "publishing")
# How recently an active row must have been touched to count as "a live tick".
# Older than this = a previous run almost certainly crashed; don't deadlock on it.
BUSY_FRESH_MINUTES = 20


# ── time helpers ──────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)).strip())
    except Exception:
        return default


# ── db reads ──────────────────────────────────────────────────────────────────
def _status(db: Any, slug: str) -> str | None:
    r = db.table("topics").select("status").eq("slug", slug).limit(1).execute().data
    return r[0]["status"] if r else None


def _is_busy(db: Any) -> str | None:
    """Return a slug if another tick appears to be mid-flight, else None.
    Lets overlapping cron fires stand down without any external lock service.
    """
    cutoff = _now() - timedelta(minutes=BUSY_FRESH_MINUTES)
    rows = (db.table("topics").select("slug,status,updated_at")
            .in_("status", list(ACTIVE_STATES)).execute().data or [])
    for r in rows:
        touched = _parse(r.get("updated_at"))
        if touched and touched > cutoff:
            return r["slug"]
    return None


def _future_scheduled_count(db: Any, now_iso: str) -> int:
    rows = (db.table("topics").select("id")
            .eq("status", "scheduled").gt("scheduled_for", now_iso).execute().data or [])
    return len(rows)


def _next_slot(db: Any, gap: timedelta, now: datetime) -> datetime:
    """The next free publish slot: one gap after the latest anchor (the furthest
    future scheduled post, or the most recent publish), never in the past.
    First post ever (no anchor) → schedule for now, so it goes out on the next tick.
    """
    anchor: datetime | None = None

    sched = (db.table("topics").select("scheduled_for")
             .eq("status", "scheduled").order("scheduled_for", desc=True)
             .limit(1).execute().data or [])
    if sched:
        anchor = _parse(sched[0].get("scheduled_for"))

    pub = (db.table("blog_posts").select("published_at")
           .not_.is_("published_at", "null").order("published_at", desc=True)
           .limit(1).execute().data or [])
    if pub:
        pub_dt = _parse(pub[0].get("published_at"))
        if pub_dt and (anchor is None or pub_dt > anchor):
            anchor = pub_dt

    if anchor is None:
        return now
    return max(anchor + gap, now)


def _pick_next_queued(db: Any) -> dict | None:
    rows = (db.table("topics").select("id,slug,title,tags")
            .eq("status", "queued").order("created_at", desc=False)
            .limit(1).execute().data or [])
    return rows[0] if rows else None


def _read_audit(db: Any, topic_id: str) -> dict:
    """Read the auditor's verdict (blog_posts.audit_json). Tolerates jsonb returned
    as a dict or a string; returns {} if absent/unparseable (treated as 'proceed')."""
    rows = (db.table("blog_posts").select("audit_json")
            .eq("topic_id", topic_id).limit(1).execute().data or [])
    raw = rows[0].get("audit_json") if rows else None
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


# ── tick stages ───────────────────────────────────────────────────────────────
def _publish_due(db: Any, orch: Any, gap: timedelta, log: list[str]) -> int:
    """Publish the single most-overdue scheduled post. Re-space any other overdue
    posts forward from now so downtime never collapses the cadence into a dump.
    """
    now = _now()
    due = (db.table("topics").select("id,slug,scheduled_for")
           .eq("status", "scheduled").lte("scheduled_for", _iso(now))
           .order("scheduled_for", desc=False).execute().data or [])
    if not due:
        return 0

    first, rest = due[0], due[1:]
    published = 0
    log.append(f"publish due: {first['slug']} (slot {first.get('scheduled_for')})")
    try:
        orch.run_publish(first["id"], first["slug"])
        log.append(f"  -> published {first['slug']}")
        published = 1
    except Exception as exc:  # run_publish already marked the topic failed
        log.append(f"  -> publish FAILED {first['slug']}: {exc}")

    slot = now + gap
    for t in rest:
        db.table("topics").update({
            "scheduled_for": _iso(slot), "updated_at": _iso(now),
        }).eq("id", t["id"]).execute()
        log.append(f"  re-spaced {t['slug']} -> {_iso(slot)}")
        slot += gap
    return published


def _produce_one(db: Any, orch: Any, topic: dict, slot: datetime, log: list[str]) -> bool:
    """Research → write the topic (auto-advancing both gates), then schedule it.
    Returns True only if it reached 'scheduled'. Any stage failure leaves the topic
    in 'failed' (the orchestrator handles that) and returns False so the caller moves on.

    Each topic is its own recorded run. That matters for more than tidy telemetry:
    MAX_RUN_COST_USD is a *per-run* ceiling, so a single recorder spanning a whole
    catch-up batch would have applied a one-post budget to the entire backlog and
    silently stalled it partway through.
    """
    from swarm.orchestrator import recorded_run

    tid, slug, title = topic["id"], topic["slug"], topic["title"]
    tags = topic.get("tags") or []
    log.append(f"produce: {slug}")

    with recorded_run(slug, tid, trigger="autopilot"):
        return _produce_one_inner(db, orch, topic, slot, log)


def _produce_one_inner(db: Any, orch: Any, topic: dict, slot: datetime, log: list[str]) -> bool:
    tid, slug, title = topic["id"], topic["slug"], topic["title"]
    tags = topic.get("tags") or []

    orch.run_research(tid, slug, title, tags)
    if _status(db, slug) != "verifying_research":
        log.append(f"  research did not complete; leaving {slug}")
        return False

    # ── Audit gate ──────────────────────────────────────────────────────────
    # run_research already ran + stored the audit verdict. On a hard 'reject',
    # re-research once, then re-audit. A topic that fails audit twice is left at
    # verifying_research (a human review item) and NOT auto-written/published.
    verdict = _read_audit(db, tid)
    rec = (verdict.get("recommendation") or "proceed").lower()
    if rec == "reject":
        log.append(f"  audit REJECTED {slug} (score={verdict.get('score')}) — re-researching once")
        orch.run_research(tid, slug, title, tags)
        if _status(db, slug) != "verifying_research":
            log.append(f"  re-research did not complete; leaving {slug}")
            return False
        verdict = _read_audit(db, tid)
        if (verdict.get("recommendation") or "proceed").lower() == "reject":
            log.append(f"  audit rejected {slug} again — holding for human review, skipping")
            return False
    log.append(f"  audit {verdict.get('recommendation', 'proceed')} "
               f"(score={verdict.get('score')}) for {slug}")

    orch.run_writing(tid, slug, title)
    if _status(db, slug) != "verifying_draft":
        log.append(f"  writing did not complete; leaving {slug}")
        return False

    db.table("topics").update({
        "status": "scheduled", "scheduled_for": _iso(slot), "updated_at": _iso(_now()),
    }).eq("id", tid).execute()
    db.table("blog_posts").update({"last_error": None}).eq("topic_id", tid).execute()
    log.append(f"  -> scheduled {slug} for {_iso(slot)}")
    return True


def _refill(db: Any, orch: Any, batch: int, log: list[str]) -> int:
    """Generate a fresh batch of topics when the roadmap queue is empty."""
    from swarm.agents.ideator import run_ideation

    existing = db.table("topics").select("slug,title").limit(2000).execute().data or []
    existing_slugs = {r["slug"] for r in existing}
    existing_titles = [r["title"] for r in existing if r.get("title")]

    log.append(f"queue empty — ideating {batch} new topics...")
    try:
        ideas = run_ideation(model=orch.model, existing_titles=existing_titles, batch=batch)
    except Exception as exc:
        log.append(f"  ideation crashed: {exc}")
        return 0

    now = _iso(_now())
    inserted = 0
    for idea in ideas:
        slug = slugify(idea["title"])
        if not slug or slug in existing_slugs:
            continue
        try:
            db.table("topics").insert({
                "slug": slug,
                "title": idea["title"],
                "status": "queued",
                "tags": idea.get("tags") or [],
                "brief": idea.get("brief") or "",
                "target_keyword": idea.get("target_keyword") or "",
                "created_at": now,
                "updated_at": now,
            }).execute()
            existing_slugs.add(slug)
            inserted += 1
            log.append(f"  + ideated: {slug}")
        except Exception as exc:
            log.append(f"  ideation insert failed for {slug}: {exc}")
    return inserted


def _maintain_buffer(db: Any, orch: Any, gap: timedelta, buffer: int,
                     ideate_batch: int, max_produce: int, log: list[str]) -> int:
    """Keep `buffer` finished posts scheduled ahead, producing at most `max_produce`
    per tick so a single tick stays bounded in runtime.
    """
    produced = 0
    attempts = 0
    max_attempts = max_produce + 3  # tolerate a couple of bad topics without stalling
    while produced < max_produce and attempts < max_attempts:
        now = _now()

        topic = _pick_next_queued(db)
        if topic is None:
            # No seeded/queued backlog left — only top up the steady-state buffer via
            # ideation (so the queue can't run dry), bounded by `buffer`.
            if _future_scheduled_count(db, _iso(now)) >= buffer:
                break
            if _refill(db, orch, ideate_batch, log) <= 0:
                log.append("nothing queued and ideation added nothing — idle")
                break
            topic = _pick_next_queued(db)
            if topic is None:
                break
        # A queued topic exists → drain it (one per tick, regardless of `buffer`) so a
        # seeded backlog gets written out steadily instead of stalling at the buffer.
        # Publishing stays on cadence because each post is scheduled a gap apart.

        slot = _next_slot(db, gap, now)
        attempts += 1
        try:
            if _produce_one(db, orch, topic, slot, log):
                produced += 1
        except Exception as exc:  # orchestrator marked it failed; try the next topic
            log.append(f"  produce crashed for {topic.get('slug')}: {exc}")
    return produced


# ── entry point ───────────────────────────────────────────────────────────────
def run_tick(orch: Any, db: Any) -> list[str]:
    """Run one autopilot tick. Returns a human-readable log (also printed by run.py)."""
    log: list[str] = [f"[autopilot] tick @ {_iso(_now())}"]

    if os.environ.get("AUTOPILOT_ENABLED", "true").strip().lower() == "false":
        log.append("AUTOPILOT_ENABLED=false — standing down (no-op)")
        return log

    gap = timedelta(hours=max(1, _env_int("PUBLISH_GAP_HOURS", 24)))
    buffer = max(1, _env_int("AUTOPILOT_BUFFER", 1))
    ideate_batch = max(1, _env_int("AUTOPILOT_IDEATE_BATCH", 8))
    max_produce = max(1, _env_int("AUTOPILOT_MAX_PRODUCE_PER_TICK", 1))
    log.append(f"config: gap={gap}, buffer={buffer}, ideate_batch={ideate_batch}, "
               f"max_produce={max_produce}")

    busy = _is_busy(db)
    if busy:
        log.append(f"another tick is mid-flight (active: {busy}) — standing down")
        return log

    published = _publish_due(db, orch, gap, log)
    produced = _maintain_buffer(db, orch, gap, buffer, ideate_batch, max_produce, log)
    log.append(f"[autopilot] done: published={published} produced={produced}")
    return log


def produce_all_queued(orch: Any, db: Any) -> list[str]:
    """One-shot catch-up: research → audit → write EVERY queued topic now, scheduling
    each on the publish cadence (24h apart) so the hourly autopilot tick then drips
    them out. This is the 'write all the stuck/queued posts now' action — published
    posts are untouched (only status='queued' topics are picked up).

    Each topic leaves 'queued' after one pass (→ scheduled, failed, or held at
    verifying_research if it fails audit twice), so the loop always terminates.
    """
    log: list[str] = [f"[produce-all] start @ {_iso(_now())}"]
    if os.environ.get("AUTOPILOT_ENABLED", "true").strip().lower() == "false":
        log.append("AUTOPILOT_ENABLED=false — standing down (no-op)")
        return log

    gap = timedelta(hours=max(1, _env_int("PUBLISH_GAP_HOURS", 24)))
    max_topics = max(1, _env_int("PRODUCE_ALL_MAX", 200))
    scheduled = 0
    for _ in range(max_topics):
        topic = _pick_next_queued(db)
        if topic is None:
            log.append("no more queued topics")
            break
        slot = _next_slot(db, gap, _now())
        try:
            if _produce_one(db, orch, topic, slot, log):
                scheduled += 1
        except SpendCeilingExceeded as exc:
            # A ceiling is a stop, not a per-topic failure. Swallowing it here
            # would turn every remaining topic into a silent no-op that still
            # looked like it had been attempted.
            log.append(f"  SPEND CEILING hit at {topic.get('slug')}: {exc}")
            log.append("  stopping the batch — raise the ceiling or run again later")
            break
        except Exception as exc:  # orchestrator marks the topic failed; move on
            log.append(f"  produce crashed for {topic.get('slug')}: {exc}")
        finally:
            # Free each topic's research/draft payloads before the next one so a long
            # catch-up doesn't accumulate RSS to the OOM line on small instances.
            gc.collect()
    log.append(f"[produce-all] done: scheduled={scheduled}")
    return log
