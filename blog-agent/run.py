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
from swarm.orchestrator import BlogOrchestrator


def _slugify(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:60]


def _db():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _ensure_topic(title: str, tags: list[str]) -> dict:
    """Create topic in Supabase if it doesn't exist. Return the record."""
    slug = _slugify(title)
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
    parser = argparse.ArgumentParser(description="Buteforce Blog Agent CLI")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--topic",   help="Start a new blog topic (runs research automatically)")
    g.add_argument("--approve", metavar="SLUG", help="Approve current stage for a topic slug")
    g.add_argument("--reject",  metavar="SLUG", help="Reject current stage for a topic slug")
    g.add_argument("--status",  metavar="SLUG", help="Print current status for a topic slug")
    g.add_argument("--list",    action="store_true", help="List all topics and their statuses")
    g.add_argument("--delete",  metavar="SLUG", help="Delete a topic and its blog post entirely")
    g.add_argument("--reset",   metavar="SLUG", help="Reset a failed topic to its last reviewable stage")

    parser.add_argument("--tags",     default="", help="Comma-separated tags (used with --topic)")
    parser.add_argument("--feedback", default="", help="Rejection feedback (used with --reject)")
    parser.add_argument("--stage",    choices=["research", "write", "publish"],
                        help="Force a specific stage to run (used with --topic on existing slug)")

    args = parser.parse_args()
    orch = BlogOrchestrator()
    db = _db()

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

        if status == "verifying_research":
            print(f"[approve] Research approved. Starting draft...")
            orch.run_writing(topic_id, slug, topic["title"])
            print(f"✓ Draft ready. Open dashboard to review.")
        elif status == "verifying_draft":
            print(f"[approve] Draft approved. Publishing...")
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
        print(f"✓ Reset '{slug}' → {target}")
        return


if __name__ == "__main__":
    main()
