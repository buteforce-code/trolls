"""
CLI entry point.
Usage:
  python run.py --topic "AI replacing junior devs" --tags "ai,jobs,engineering"
  python run.py --topic "..." --stage research   # run only research
  python run.py --approve <slug>                 # approve current stage
  python run.py --reject  <slug> --feedback "..." # reject and re-run
  python run.py --list-failed                    # what is stranded, and why (free)
  python run.py --resume-failed                  # re-run the writer on stranded
                                                 # topics, reusing stored research
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Force UTF-8 stdout on Windows to avoid CP1252 encoding errors
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from supabase import create_client
from swarm import guards
from swarm.orchestrator import BlogOrchestrator, recorded_run
from swarm.slugs import slugify


def _db():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _ensure_topic(title: str, tags: list[str]) -> dict:
    """Create topic in Supabase if it doesn't exist. Return the record."""
    slug = slugify(title)
    db = _db()
    existing = db.table("topics").select("*").eq("slug", slug).limit(1).execute()
    if existing.data:
        print(f"[run] Topic already exists: {slug}")
        return existing.data[0]

    now = datetime.utcnow().isoformat() + "Z"
    result = db.table("topics").insert({
        "slug": slug,
        "title": title,
        "status": "queued",
        "tags": tags,
        "created_at": now,
        "updated_at": now,
    }).execute()
    if not result.data:
        raise RuntimeError(f"Failed to insert topic: {slug}")
    print(f"[run] Created topic: {slug}")
    return result.data[0]


def main():
    parser = argparse.ArgumentParser(description="Trolls — Marketing Agent Swarm CLI")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--topic",   help="Start a new blog topic (runs research automatically)")
    g.add_argument("--approve", metavar="SLUG", help="Approve current stage for a topic slug")
    g.add_argument("--reject",  metavar="SLUG", help="Reject current stage for a topic slug")
    g.add_argument("--status",  metavar="SLUG", help="Print current status for a topic slug")
    g.add_argument("--list",    action="store_true", help="List all topics and their statuses")
    g.add_argument("--delete",  metavar="SLUG", help="Delete a topic and its blog post entirely")
    g.add_argument("--reset",   metavar="SLUG", help="Reset a failed topic to its last reviewable stage")
    g.add_argument("--autopilot", action="store_true",
                   help="Run one autonomous tick: publish due posts, keep the buffer full, refill the queue")
    g.add_argument("--produce-all", action="store_true", dest="produce_all",
                   help="Catch-up: research+audit+write EVERY queued topic now and schedule them on cadence")
    g.add_argument("--ingest-analytics", action="store_true", dest="ingest_analytics",
                   help="Pull Search Console + GA4 performance data for every published post")
    g.add_argument("--check-analytics", action="store_true", dest="check_analytics",
                   help="Probe analytics credentials and property config without writing anything")
    g.add_argument("--learn", action="store_true",
                   help="Score every published post, fit the bandit, and rank the queue")
    g.add_argument("--scout", action="store_true",
                   help="Sweep trend sources, gate them against the brand, and store scored signals")
    g.add_argument("--distribute", action="store_true",
                   help="One distribution tick: schedule published posts, send at most one")
    g.add_argument("--distribution-queue", action="store_true", dest="distribution_queue",
                   help="Show what is scheduled to go out and when")
    g.add_argument("--mark-posted", metavar="ID", dest="mark_posted",
                   help="Record that you posted a queued send by hand")
    g.add_argument("--health", action="store_true",
                   help="Report engine liveness; exits non-zero if anything is stalled")
    g.add_argument("--list-failed", action="store_true", dest="list_failed",
                   help="Show every failed topic and which stage it could resume at. Spends nothing")
    g.add_argument("--resume-failed", action="store_true", dest="resume_failed",
                   help="Re-run the writer for failed topics that already have research, "
                        "reusing the stored digest instead of researching again")

    parser.add_argument("--tags",     default="", help="Comma-separated tags (used with --topic)")
    parser.add_argument("--feedback", default="", help="Rejection feedback (used with --reject)")
    parser.add_argument("--stage",    choices=["research", "write", "publish"],
                        help="Force a specific stage to run (used with --topic on existing slug)")
    parser.add_argument("--days", type=int, default=None,
                        help="Trailing window for --ingest-analytics (default ANALYTICS_INGEST_DAYS, or 90 to backfill)")
    parser.add_argument("--slugs", default="",
                        help="Comma-separated slugs to limit --resume-failed to (default: all of them)")
    parser.add_argument("--limit", type=int, default=100,
                        help="Cap on topics touched by --list-failed / --resume-failed")

    args = parser.parse_args()

    # ── Analytics ─────────────────────────────────────────────────────────────
    # Handled before BlogOrchestrator is constructed: ingestion is pure data
    # movement and has no business paying the cost of spinning up the LLM agents.
    if args.check_analytics:
        from swarm.analytics.ingest import check
        for line in check():
            print(line, flush=True)
        return

    if args.ingest_analytics:
        from swarm.analytics.ingest import run_ingest
        from swarm.jobs import run_and_record
        from swarm.learning.engine import run_learning

        db = _db()
        run_and_record(db, "ingest-analytics", lambda: run_ingest(db, days=args.days))

        # Learn immediately after, in the same process. Chaining here rather than
        # as a second scheduled job guarantees the ordering: beliefs are always
        # derived from the data that was just fetched, never from yesterday's.
        # It is pure computation over stored rows, so it costs nothing extra.
        try:
            run_and_record(db, "learn", lambda: run_learning(db))
        except Exception as exc:
            print(f"[learning] FAILED after ingest: {exc}", flush=True)
        return

    # HTTP fetches plus deterministic scoring — no agents, no LLM calls.
    if args.scout:
        from swarm.jobs import health_report, run_and_record
        from swarm.trends.scout import run_scout

        db = _db()
        run_and_record(db, "scout", lambda: run_scout(db))
        # Liveness rides along with the sweep rather than needing its own cron.
        # The scout runs hourly and costs nothing, so it is the cheapest place to
        # notice that the engine has stopped — and a failing health check makes
        # this job report ok=False, which turns the Actions workflow red.
        run_and_record(db, "health", lambda: health_report(db))
        return

    # Distribution: HTTP only, no agents, no LLM calls. Before the orchestrator for the same
    # reason --health is: shipping the kits already written must not require a writer model.
    if args.distribute:
        from swarm.distribute.queue import run_tick as distribute_tick
        from swarm.jobs import run_and_record

        db = _db()
        run_and_record(db, "distribute", lambda: distribute_tick(db))
        return

    if args.distribution_queue:
        from swarm.distribute.queue import describe as describe_queue

        for line in describe_queue(_db(), limit=args.limit):
            print(line, flush=True)
        return

    if args.mark_posted:
        from swarm.distribute.queue import mark_posted

        for line in mark_posted(_db(), args.mark_posted):
            print(line, flush=True)
        return

    # Read-only liveness check. Deliberately before the orchestrator is built:
    # "is my engine alive" must be answerable without every provider key present.
    if args.health:
        from swarm.jobs import health_report as _report

        lines = _report(_db())
        for line in lines:
            print(line, flush=True)
        sys.exit(1 if any(line.startswith("! ") for line in lines) else 0)

    # Read-only inventory of what is stranded. Deliberately before the orchestrator
    # is built: an operator asking "what is stuck and what will it cost me" should
    # not have to satisfy every provider key check to get an answer.
    if args.list_failed:
        from swarm.recovery import describe

        for line in describe(_db(), limit=args.limit):
            print(line, flush=True)
        return

    # Pure computation over already-stored metrics — no agents, no LLM calls.
    if args.learn:
        from swarm.jobs import run_and_record
        from swarm.learning.engine import run_learning

        db = _db()
        run_and_record(db, "learn", lambda: run_learning(db))
        return

    # Validate any slug before it reaches a database filter or a log path. The
    # dashboard passes these through from HTTP, so "it came from our own UI" is
    # not a guarantee about their shape.
    for value in (args.approve, args.reject, args.status, args.delete, args.reset):
        if value and not guards.is_valid_slug(value):
            print(f"Invalid slug: {value!r}")
            sys.exit(2)

    orch = BlogOrchestrator()
    db = _db()

    # ── Autopilot (one autonomous tick) ───────────────────────────────────────
    # Autopilot opens one recorded run *per topic* (see autopilot._produce_one),
    # not one for the whole tick — a per-run spend ceiling applied to a whole
    # catch-up batch would stall the backlog partway through.
    if args.autopilot:
        from swarm.autopilot import run_tick
        for line in run_tick(orch, db):
            print(line, flush=True)
        return

    # ── Resume failed topics at the writer ────────────────────────────────────
    # Autopilot never picks a `failed` topic back up (see swarm/recovery.py), so
    # without this they stay stranded with their paid-for research intact. The
    # batch stops on the first ProviderBlocked rather than marching the rest of
    # the list into the same wall.
    if args.resume_failed:
        from swarm.recovery import resume

        slugs = [s.strip() for s in args.slugs.split(",") if s.strip()]
        for value in slugs:
            if not guards.is_valid_slug(value):
                print(f"Invalid slug: {value!r}")
                sys.exit(2)
        for line in resume(orch, db, slugs=slugs or None, limit=args.limit):
            print(line, flush=True)
        return

    # ── Produce-all (one-shot catch-up of every queued topic) ─────────────────
    if args.produce_all:
        from swarm.autopilot import produce_all_queued
        for line in produce_all_queued(orch, db):
            print(line, flush=True)
        return

    # ── List ────────────────────────────────────────────────────────────────
    if args.list:
        rows = db.table("topics").select("slug,title,status,tags,updated_at")\
            .order("updated_at", desc=True).limit(20).execute().data
        if not rows:
            print("No topics yet.")
            return
        print(f"\n{'SLUG':<40} {'STATUS':<25} {'TAGS'}")
        print("-" * 80)
        for r in rows:
            tags = ", ".join(r.get("tags") or [])
            print(f"{r['slug']:<40} {r['status']:<25} {tags}")
        return

    # ── Status ───────────────────────────────────────────────────────────────
    if args.status:
        r = db.table("topics").select("*").eq("slug", args.status).limit(1).execute()
        if not r.data:
            print(f"Topic '{args.status}' not found.")
            return
        t = r.data[0]
        print(json.dumps({k: t[k] for k in ["slug", "title", "status", "tags", "updated_at"]}, indent=2))
        return

    # ── New Topic → Research ─────────────────────────────────────────────────
    if args.topic:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        topic = _ensure_topic(args.topic, tags)
        topic_id = topic["id"]
        slug = topic["slug"]
        title = topic["title"]

        stage = args.stage or "research"
        with recorded_run(slug, topic_id, trigger="cli"):
            if stage == "research":
                orch.run_research(topic_id, slug, title, tags)
                print(f"\n✓ Research complete. Open the dashboard to review.")
                print(f"  slug: {slug}")
            elif stage == "write":
                orch.run_writing(topic_id, slug, title)
                print(f"\n✓ Draft ready. Open the dashboard to review.")
            elif stage == "publish":
                orch.run_publish(topic_id, slug)
                print(f"\n✓ Published.")
        return

    # ── Approve ──────────────────────────────────────────────────────────────
    if args.approve:
        slug = args.approve
        r = db.table("topics").select("*").eq("slug", slug).limit(1).execute()
        if not r.data:
            print(f"Topic '{slug}' not found.")
            sys.exit(1)
        topic = r.data[0]
        status = topic["status"]
        topic_id = topic["id"]

        with recorded_run(slug, topic_id, trigger="dashboard"):
            if status == "verifying_research":
                print(f"[approve] Research approved. Starting draft...")
                orch.run_writing(topic_id, slug, topic["title"])
                print(f"✓ Draft ready. Open dashboard to review.")
            elif status in ("verifying_draft", "scheduled"):
                # 'scheduled' = autopilot has it queued for a future slot; approving
                # means "publish now" instead of waiting out the veto window.
                label = "Draft approved" if status == "verifying_draft" else "Publishing ahead of schedule"
                print(f"[approve] {label}. Publishing...")
                result = orch.run_publish(topic_id, slug)
                if result.get("published") or result.get("dry_run"):
                    url = result.get("published_url", "(dry run)")
                    print(f"✓ Published: {url}")
                else:
                    print(f"✗ Publish failed: {result.get('error')}")
                    sys.exit(1)
            else:
                print(f"Nothing to approve at status '{status}'.")
        return

    # ── Reject ───────────────────────────────────────────────────────────────
    if args.reject:
        slug = args.reject
        r = db.table("topics").select("*").eq("slug", slug).limit(1).execute()
        if not r.data:
            print(f"Topic '{slug}' not found.")
            sys.exit(1)
        topic = r.data[0]
        feedback = args.feedback or "No specific feedback given."
        print(f"[reject] Rejecting '{slug}' at '{topic['status']}' with feedback: {feedback}")
        orch.handle_rejection(topic["id"], slug, topic["status"], feedback)
        print(f"✓ Re-run complete.")
        return

    # ── Delete ───────────────────────────────────────────────────────────────
    if args.delete:
        slug = args.delete
        r = db.table("topics").select("id").eq("slug", slug).limit(1).execute()
        if not r.data:
            print(f"Topic '{slug}' not found.")
            sys.exit(1)
        topic_id = r.data[0]["id"]
        db.table("blog_posts").delete().eq("topic_id", topic_id).execute()
        db.table("topics").delete().eq("id", topic_id).execute()
        print(f"✓ Deleted topic: {slug}")
        return

    # ── Reset ────────────────────────────────────────────────────────────────
    if args.reset:
        slug = args.reset
        r = db.table("topics").select("id,status").eq("slug", slug).limit(1).execute()
        if not r.data:
            print(f"Topic '{slug}' not found.")
            sys.exit(1)
        topic_id = r.data[0]["id"]
        post_r = db.table("blog_posts").select("research_json,mdx_final") \
                   .eq("topic_id", topic_id).limit(1).execute()
        post = post_r.data[0] if post_r.data else {}
        if post.get("mdx_final"):
            target = "verifying_draft"
        elif post.get("research_json"):
            target = "verifying_research"
        else:
            target = "queued"
        db.table("topics").update({
            "status": target,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }).eq("id", topic_id).execute()
        # Clear any stale crash message so the UI doesn't keep showing it.
        db.table("blog_posts").update({"last_error": None}).eq("topic_id", topic_id).execute()
        print(f"✓ Reset '{slug}' → {target}")
        return


if __name__ == "__main__":
    main()
