"""
CLI entry point.
Usage:
  python run.py --topic "AI replacing junior devs" --tags "ai,jobs,engineering"
  python run.py --topic "..." --stage research   # run only research
  python run.py --approve <slug>                 # approve current stage
  python run.py --reject  <slug> --feedback "..." # reject and re-run
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

    parser.add_argument("--tags",     default="", help="Comma-separated tags (used with --topic)")
    parser.add_argument("--feedback", default="", help="Rejection feedback (used with --reject)")
    parser.add_argument("--stage",    choices=["research", "write", "publish"],
                        help="Force a specific stage to run (used with --topic on existing slug)")
    parser.add_argument("--days", type=int, default=None,
                        help="Trailing window for --ingest-analytics (default ANALYTICS_INGEST_DAYS, or 90 to backfill)")

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
        from swarm.jobs import run_and_record
        from swarm.trends.scout import run_scout

        db = _db()
        run_and_record(db, "scout", lambda: run_scout(db))
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
