"""Recovery — re-enter a failed topic at the stage it actually died at.

Why this exists
---------------
Autopilot never looks at a failed topic again. ``_pick_next_queued`` filters on
``status = 'queued'`` and ``_publish_due`` on ``status = 'scheduled'``; nothing in
the tick selects ``failed``. So a topic that dies mid-pipeline is stranded
permanently, and the only route back was a human running ``--reset`` and then
``--approve``, one slug at a time, from a terminal.

That was survivable while failures were one-offs. On 2026-08-27 eight topics
failed together on a single OpenRouter 402 (see ``swarm/failures.py``), every one
of them with a complete, already-paid-for research digest sitting in
``blog_posts.research_json`` — 5,750–7,656 characters each — and a NULL
``mdx_draft``. Re-running those from scratch would pay the research bill twice
for work that never went wrong.

So this module answers one question: which failed topics can be resumed *without*
redoing the expensive part, and where does each resume from?

    stranded(db)          → the failed topics and the stage each should re-enter at
    resume(orch, db, ...) → actually re-enter them, stopping the batch on a
                            ProviderBlocked rather than repeating the mistake

The resume path deliberately re-enters at the *writer* rather than at research.
``BlogOrchestrator._run_writing_inner`` already reads ``research_json`` off the
stored row, so the resume needs no new pipeline — only the decision of where to
come back in.

Recovered topics are left at ``verifying_draft``, the normal human review gate,
not auto-scheduled. A batch that was rescued after an incident is exactly the
batch a person should look at before it publishes itself.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator

from swarm.failures import ProviderBlocked, classify

# Where a failed topic should come back in, given what survived on its row.
STAGE_WRITE = "write"        # research is good; re-run the writer
STAGE_PUBLISH = "publish"    # a finished draft exists; only publishing failed
STAGE_RESEARCH = "research"  # nothing usable survived; start over (costs full price)

# How much research text counts as "a real digest". The eight stranded rows carry
# 5,750–7,656 characters; a few hundred characters is a truncated or error-shaped
# payload that would produce a thin post, and paying the writer to discover that
# is worse than paying research again.
MIN_RESEARCH_CHARS = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _research_len(post: dict) -> int:
    raw = post.get("research_json")
    if raw is None:
        return 0
    return len(raw if isinstance(raw, str) else str(raw))


def resume_stage(post: dict) -> str:
    """Which stage this failed topic should re-enter at, from its surviving artefacts.

    Ordered most-progress-first, so a topic that got further is never sent back
    further than it has to go.
    """
    if post.get("mdx_final"):
        return STAGE_PUBLISH
    if _research_len(post) >= MIN_RESEARCH_CHARS:
        return STAGE_WRITE
    return STAGE_RESEARCH


def stranded(db: Any, limit: int = 100) -> list[dict]:
    """Every ``failed`` topic, with the stage it should resume at and why.

    Read-only. Safe to call before deciding whether to spend anything — which is
    the point: the operator sees the bill before it is incurred.
    """
    topics = (db.table("topics").select("id,slug,title,tags,status")
              .eq("status", "failed").order("updated_at", desc=False)
              .limit(limit).execute().data or [])
    if not topics:
        return []

    out: list[dict] = []
    for topic in topics:
        rows = (db.table("blog_posts")
                .select("research_json,mdx_draft,mdx_final,word_count,last_error")
                .eq("topic_id", topic["id"]).limit(1).execute().data or [])
        post = rows[0] if rows else {}
        verdict = classify(post.get("last_error") or "")
        out.append({
            **topic,
            "stage": resume_stage(post),
            "research_chars": _research_len(post),
            "has_draft": bool(post.get("mdx_draft")),
            "last_error": post.get("last_error"),
            "failure_kind": verdict.kind,
        })
    return out


def describe(db: Any, limit: int = 100) -> list[str]:
    """Human-readable plan. Spends nothing."""
    rows = stranded(db, limit)
    if not rows:
        return ["[recovery] no failed topics — nothing to resume"]

    lines = [f"[recovery] {len(rows)} failed topic(s):"]
    for row in rows:
        lines.append(
            f"  {row['slug']}  → resume at {row['stage']} "
            f"(research {row['research_chars']} chars, "
            f"draft {'yes' if row['has_draft'] else 'no'}, "
            f"last failure: {row['failure_kind']})"
        )
    kinds = {row["failure_kind"] for row in rows}
    if "credits" in kinds:
        lines.append(
            "  ⚠ at least one of these died on a billing block. Top the provider up "
            "BEFORE resuming, or the resume will fail on the first topic and stop."
        )
    return lines


def resume(
    orch: Any,
    db: Any,
    slugs: list[str] | None = None,
    limit: int = 100,
    stages: tuple[str, ...] = (STAGE_WRITE,),
) -> Iterator[str]:
    """Re-enter each stranded topic at its stage. Yields a log line at a time.

    ``stages`` defaults to write-only on purpose. That is the case this exists for
    — research paid for, draft never written — and it is the only one that is
    unambiguously cheap. Resuming a ``research`` topic costs the same as starting
    it fresh, so it has to be asked for explicitly.

    A ``ProviderBlocked`` stops the whole batch. That is the entire lesson of the
    incident: eight topics failed one after another on a condition that was
    already true when the first one failed, and each attempt burned what was left
    of the balance. This loop refuses to repeat it.
    """
    candidates = stranded(db, limit)
    if slugs:
        wanted = set(slugs)
        candidates = [c for c in candidates if c["slug"] in wanted]
        missing = wanted - {c["slug"] for c in candidates}
        for slug in sorted(missing):
            yield f"  skip {slug}: not a failed topic (already recovered, or never failed)"

    todo = [c for c in candidates if c["stage"] in stages]
    skipped = [c for c in candidates if c["stage"] not in stages]
    for row in skipped:
        yield (f"  skip {row['slug']}: would need to resume at '{row['stage']}', "
               f"which is not in {list(stages)}")

    if not todo:
        yield "[recovery] nothing to resume"
        return

    yield f"[recovery] resuming {len(todo)} topic(s) at: {', '.join(sorted(stages))}"
    recovered = 0
    for row in todo:
        slug, tid, title = row["slug"], row["id"], row["title"]
        yield f"  {slug}: re-entering at {row['stage']} "\
              f"(reusing {row['research_chars']} chars of stored research)"
        try:
            _resume_one(orch, db, row)
        except ProviderBlocked as exc:
            # Not this topic's fault and not fixable by moving on.
            yield f"  ✗ {slug}: {exc}"
            yield ("[recovery] STOPPING — the provider is blocked, every remaining "
                   "topic would fail identically. Fix the account, then re-run.")
            yield f"[recovery] done: recovered={recovered}, remaining={len(todo) - recovered - 1}"
            return
        except Exception as exc:
            # Per-topic failure. The orchestrator has already written last_error
            # and set status=failed, so this stays visible in the dashboard.
            yield f"  ✗ {slug}: {classify(exc).kind} — {exc}"
            continue
        recovered += 1
        yield f"  ✓ {slug}: now at '{_status(db, slug)}'"

    yield f"[recovery] done: recovered={recovered} of {len(todo)}"


def _resume_one(orch: Any, db: Any, row: dict) -> None:
    """Run the one stage this topic needs. Raises on failure — the caller decides."""
    from swarm.orchestrator import recorded_run

    tid, slug, title = row["id"], row["slug"], row["title"]
    stage = row["stage"]

    # One recorded run per topic, same as autopilot._produce_one — MAX_RUN_COST_USD
    # is a per-run ceiling, and a single recorder over the whole rescue batch would
    # apply one post's budget to eight of them.
    with recorded_run(slug, tid, trigger="recovery"):
        if stage == STAGE_WRITE:
            orch.run_writing(tid, slug, title)
        elif stage == STAGE_PUBLISH:
            orch.run_publish(tid, slug)
        elif stage == STAGE_RESEARCH:
            orch.run_research(tid, slug, title, row.get("tags") or [])
        else:
            raise ValueError(f"Unknown resume stage {stage!r} for {slug}")

    # The stale crash message would otherwise sit on the row forever and keep the
    # dashboard showing a failure that has been fixed.
    db.table("blog_posts").update({"last_error": None}).eq("topic_id", tid).execute()
    db.table("topics").update({"updated_at": _now_iso()}).eq("id", tid).execute()


def _status(db: Any, slug: str) -> str:
    rows = db.table("topics").select("status").eq("slug", slug).limit(1).execute().data or []
    return rows[0]["status"] if rows else "unknown"
