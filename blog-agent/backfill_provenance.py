"""One-shot backfill of `topics.source_kind` / `source_detail` for topics created
before provenance was recorded.

Provenance is only useful to the learning layer if it covers the whole history —
a scorer that can see the origin of new posts but not the twelve already
published would compare "ideator topics" against a null class rather than
against roadmap seeds.

Attribution is derived from evidence, never guessed:

  roadmap_seed  the title appears in one of the seed scripts (the actual origin)
  human         everything else, all of which predates any automated ideation

The one topic with a known external origin — the Sarvam post, which came from a
LinkedIn find — is recorded explicitly, because it is currently the site's best
performer and the single most valuable data point the learning layer has.

Safe to re-run. Only fills rows where source_kind IS NULL, so a correction made
by hand afterwards is never overwritten.

Usage:
  python backfill_provenance.py --dry-run
  python backfill_provenance.py
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from swarm.slugs import slugify


def _db():
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv(Path(__file__).resolve().parent / ".env")
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


# Topics whose origin is known first-hand rather than inferable from the repo.
KNOWN_ORIGINS: dict[str, dict] = {
    "sarvam-code-the-claude-code-and-codex-rival": {
        "source_kind": "human",
        "source_detail": {
            "platform": "linkedin",
            "url": "",
            "signal": "Founder saw Sarvam's AI coding agent discussed on LinkedIn and "
                      "wrote the post the same week.",
            "why_now": "Newsjacked a launch while search demand was forming and "
                       "no established page ranked for it yet.",
            "note": "Recorded from the founder's own account of how the post came about. "
                    "Best-performing post on the site as of 2026-08-06.",
        },
    },
}


def _normalise_title(text: str) -> str:
    """Lowercase alphanumeric-only form, for comparing titles across sources."""
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def _seeded_titles() -> dict[str, str]:
    """{normalised title: which seed script it came from}.

    Matched on title rather than slug on purpose. Most of these topics were
    seeded before the slug bug was fixed (see tests/test_slugs.py), so their
    stored slugs were cut mid-word by the old `slug[:60]` and re-slugifying the
    same title today produces a different, longer string. Titles did not change,
    so they are the only stable join key back to the seed scripts.

    Reading the seed scripts rather than matching on dates: several roadmaps were
    loaded on the same day as hand-written posts, so a date heuristic would
    mislabel them.
    """
    out: dict[str, str] = {}
    sources = (
        ("seed_topics", "ROADMAP", 0),
        ("seed_cluster_expansion", "CLUSTER", 0),
        # seed_geo_targets rows are (slug, title, keyword, tags, brief) — the
        # title is the second element, not the first.
        ("seed_geo_targets", "TARGETS", 1),
    )
    for module_name, attr, title_index in sources:
        try:
            module = __import__(module_name)
            rows = getattr(module, attr, [])
        except Exception as exc:
            print(f"  ! could not read {module_name}.{attr}: {exc}")
            continue
        for row in rows:
            if not row or len(row) <= title_index:
                continue
            key = _normalise_title(row[title_index])
            if key:
                out.setdefault(key, module_name)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill topic provenance")
    parser.add_argument("--dry-run", action="store_true", help="print, change nothing")
    args = parser.parse_args()

    db = _db()
    seeded = _seeded_titles()
    print(f"seed scripts define {len(seeded)} titles")

    topics = (db.table("topics").select("slug,title,status,source_kind")
              .limit(5000).execute().data or [])
    todo = [t for t in topics if not t.get("source_kind")]
    print(f"{len(topics)} topics, {len(todo)} without provenance\n")

    now = datetime.now(timezone.utc).isoformat()
    counts: dict[str, int] = {}

    for topic in todo:
        slug = topic["slug"]

        title_key = _normalise_title(topic.get("title") or "")

        if slug in KNOWN_ORIGINS:
            kind = KNOWN_ORIGINS[slug]["source_kind"]
            detail = dict(KNOWN_ORIGINS[slug]["source_detail"])
        elif title_key in seeded:
            kind = "roadmap_seed"
            detail = {
                "platform": "own_analysis",
                "url": "",
                "signal": f"Seeded from the editorial roadmap in {seeded[title_key]}.",
                "why_now": "",
            }
        else:
            kind = "human"
            detail = {
                "platform": "own_analysis",
                "url": "",
                "signal": "Created before provenance was recorded; exact origin unknown.",
                "why_now": "",
                "note": "Backfilled. Treat as low-confidence when grouping by source.",
            }

        detail["captured_at"] = now
        detail["backfilled"] = True
        counts[kind] = counts.get(kind, 0) + 1

        print(f"  {kind:<13} {slug[:64]}")
        if not args.dry_run:
            db.table("topics").update({
                "source_kind": kind, "source_detail": detail,
            }).eq("slug", slug).execute()

    print("\nsummary: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if args.dry_run:
        print("dry run — nothing written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
