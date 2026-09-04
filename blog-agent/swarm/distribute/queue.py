"""The distribution queue — enqueue, drain, record.

Split from the policy in `__init__.py` so the scheduling rules stay testable without a
database. This half is the part that talks to Postgres and to a provider, and it follows the
rule the rest of the pipeline follows: a failure is recorded and reported, never swallowed and
never allowed to fail the tick that called it. Distribution is the newest and least proven
thing in this repo; it must not be able to stop publishing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from swarm import distribute
from swarm.distribute import FAILED, QUEUED, SENT, SKIPPED, Send

TABLE = "distribution_queue"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _post_url(site_url: str, slug: str) -> str:
    return f"{site_url.rstrip('/')}/blog/{slug}"


def enqueue_published(db: Any, log: list[str], limit: int = 50) -> int:
    """Schedule the social kit of every published post that has not been scheduled yet.

    Idempotent on (slug, channel, variant): re-running a tick cannot double-post, which is
    the single failure that would make an autonomous poster unusable. Postgres enforces it as
    a unique constraint, so the guarantee survives two ticks racing rather than depending on
    this read-then-write staying atomic.
    """
    from swarm import brand

    profile = brand.active()

    try:
        posts = (db.table("blog_posts")
                 .select("topic_id,published_at,social_json")
                 .not_.is_("published_at", "null")
                 .not_.is_("social_json", "null")
                 .order("published_at", desc=True).limit(limit).execute().data or [])
    except Exception as exc:
        log.append(f"  ! could not read published posts: {exc}")
        return 0

    try:
        known = {(r["slug"], r["channel"], r["variant"]) for r in
                 (db.table(TABLE).select("slug,channel,variant").limit(5000).execute().data or [])}
    except Exception as exc:
        log.append(f"  ! could not read the distribution queue: {exc}")
        return 0

    # topic_id -> slug, in one read rather than one per post.
    try:
        topics = {r["id"]: r["slug"] for r in
                  (db.table("topics").select("id,slug").limit(5000).execute().data or [])}
    except Exception as exc:
        log.append(f"  ! could not read topics: {exc}")
        return 0

    rows: list[dict] = []
    for post in posts:
        slug = topics.get(post.get("topic_id"))
        published_at = _parse(post.get("published_at"))
        if not slug or not published_at:
            continue
        kit = distribute.load_kit(post.get("social_json"))
        if not kit:
            continue
        for send in distribute.plan_for(slug, kit, published_at,
                                        url=_post_url(profile.site_url, slug)):
            if send.key in known:
                continue
            known.add(send.key)
            rows.append(send.as_row())

    if not rows:
        return 0
    try:
        db.table(TABLE).insert(rows).execute()
    except Exception as exc:
        log.append(f"  ! could not enqueue {len(rows)} sends: {exc}")
        return 0
    log.append(f"  scheduled {len(rows)} new sends across {len({r['slug'] for r in rows})} posts")
    return len(rows)


def _pending(db: Any) -> list[tuple[dict, Send]]:
    rows = (db.table(TABLE).select("*").eq("status", QUEUED)
            .order("due_at").limit(500).execute().data or [])
    out: list[tuple[dict, Send]] = []
    for row in rows:
        due = _parse(row.get("due_at"))
        if due is None:
            continue
        out.append((row, Send(row["slug"], row["channel"], row["variant"],
                              row.get("body") or "", due, QUEUED)))
    return out


def _last_sent_at(db: Any) -> datetime | None:
    rows = (db.table(TABLE).select("sent_at").eq("status", SENT)
            .not_.is_("sent_at", "null")
            .order("sent_at", desc=True).limit(1).execute().data or [])
    return _parse(rows[0]["sent_at"]) if rows else None


def _mark(db: Any, row_id: Any, status: str, external_id: str = "", error: str = "") -> None:
    patch: dict[str, Any] = {"status": status, "updated_at": _now().isoformat()}
    if status == SENT:
        patch["sent_at"] = _now().isoformat()
        patch["external_id"] = external_id or None
    if error:
        patch["error"] = error[:1000]
    db.table(TABLE).update(patch).eq("id", row_id).execute()


def run_tick(db: Any, log: list[str] | None = None) -> list[str]:
    """One distribution tick: schedule what is new, send at most one thing.

    At most one, deliberately. The cron fires hourly and the queue can hold weeks of backlog;
    draining it as fast as the cron runs would empty a month of content into an afternoon,
    which is both bad for reach and unmistakably automated. `DISTRIBUTE_GAP_HOURS` is the
    same kind of floor `publish_gap_hours` is, for the same reason.
    """
    log = log if log is not None else []
    log.append("[distribute] tick")

    pol = distribute.policy()
    if not pol.enabled:
        log.append("  DISTRIBUTE_PROVIDER=none — nothing to do")
        return log

    enqueue_published(db, log)

    try:
        pending = _pending(db)
        last = _last_sent_at(db)
    except Exception as exc:
        log.append(f"  ! could not read the queue: {exc}")
        return log

    item = distribute.next_due([s for _, s in pending], pol.gap_hours, last)
    if item is None:
        waiting = len(pending)
        log.append(f"  nothing due ({waiting} queued, gap {pol.gap_hours}h)")
        return log

    row = next(r for r, s in pending if s.key == item.key)

    if pol.dry_run:
        log.append(f"  DRY RUN — would post {item.channel}/{item.variant} for {item.slug} "
                   f"({len(item.body)} chars). Set DISTRIBUTE_DRY_RUN=false to send.")
        log.append("  " + item.body[:200].replace("\n", " ") + "…")
        return log

    from swarm.distribute.providers import resolve_provider

    provider = resolve_provider()
    try:
        result = provider.send(item)
    except Exception as exc:
        result = type("R", (), {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                                "external_id": "", "manual": False})()

    if getattr(result, "manual", False):
        # The manual provider does everything except the API call, so the item stays queued
        # and the operator is shown exactly what to paste. Marking it sent here would be a
        # lie the dashboard would then repeat.
        log.append(f"  MANUAL — ready to post to {item.channel} ({item.variant}) for {item.slug}:")
        log.append("  " + "-" * 68)
        for line in item.body.splitlines():
            log.append("  " + line)
        log.append("  " + "-" * 68)
        log.append(f"  mark it done with: python run.py --mark-posted {row['id']}")
        return log

    if result.ok:
        _mark(db, row["id"], SENT, external_id=result.external_id)
        log.append(f"  sent {item.channel}/{item.variant} for {item.slug} "
                   f"({result.external_id or 'no id returned'})")
    else:
        _mark(db, row["id"], FAILED, error=result.error)
        log.append(f"  ! send FAILED for {item.slug} ({item.channel}/{item.variant}): {result.error}")
    return log


def mark_posted(db: Any, row_id: str, log: list[str] | None = None) -> list[str]:
    """Record that a human posted a queued item. The manual provider's other half."""
    log = log if log is not None else []
    try:
        _mark(db, row_id, SENT, external_id="manual")
        log.append(f"[distribute] marked {row_id} as posted")
    except Exception as exc:
        log.append(f"[distribute] ! could not mark {row_id}: {exc}")
    return log


def describe(db: Any, limit: int = 20) -> list[str]:
    """Read-only view of the queue, for the CLI and the dashboard."""
    lines = ["[distribute] queue"]
    try:
        rows = (db.table(TABLE).select("id,slug,channel,variant,status,due_at")
                .order("due_at").limit(limit).execute().data or [])
    except Exception as exc:
        return lines + [f"  ! {exc}"]
    if not rows:
        return lines + ["  empty — run a tick to schedule published posts"]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        lines.append(f"  {str(r['due_at'])[:16]}  {r['status']:8s} {r['channel']:9s} "
                     f"{r['variant']:16s} {r['slug'][:38]}")
    lines.append("  " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    return lines
