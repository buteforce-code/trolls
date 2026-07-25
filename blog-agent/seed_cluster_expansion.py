"""
Seed the GSC-driven cluster-expansion batch into Supabase as queued topics.

WHY THIS EXISTS
Google Search Console (2026-07) showed the manufacturing / computer-vision cluster
generating 100% of Buteforce's non-brand impressions off just TWO published posts —
the FMCG computer-vision page alone is ~60% of all visibility. The cluster is proven
and under-supplied. This batch feeds it: a hub-and-spoke of FMCG packaging-line
inspection posts written to the real defect-level buyer long-tails (seal, fill, cap,
date-code, label, multi-SKU changeover) that competitors already rank for.

Source signal: config/gsc-signals.md.
Same table + idempotent upsert-by-slug contract as seed_topics.py, kept in a separate
file so the tested 24-post roadmap is untouched. Nothing publishes on seed — topics
land as `queued`; the autopilot 24h veto window still governs anything that ships.

Usage:
  python seed_cluster_expansion.py            # insert/refresh the batch
  python seed_cluster_expansion.py --dry-run  # print the plan, write nothing
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from swarm.slugs import slugify


def _db():
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv(Path(__file__).resolve().parent / ".env")
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


# title, target_keyword, tags, brief(angle)
# Hub-and-spoke: topic [1] is the pillar the existing FMCG post links UP to; the rest are
# defect-level spokes that link sideways to each other and up to the pillar.
CLUSTER: list[tuple[str, str, list[str], str]] = [
    ("Computer Vision Inspection for FMCG Packaging Lines in India: The 2026 Guide",
     "computer vision packaging inspection India",
     ["computer-vision", "fmcg", "packaging", "india"],
     "PILLAR / hub post for the FMCG inspection cluster — the page every defect-level spoke "
     "links up to, and the internal-link target that lifts the existing FMCG page off page 2. "
     "Covers the whole line: seal, fill, cap, date-code, label, multi-SKU changeover, at "
     "Indian FMCG line speeds (120+ CPM). Ties to real deployments (99.2% accuracy) and the "
     "Chennai corridor. High commercial intent for FMCG quality/plant heads."),

    ("Sachet Seal Inspection with AI Vision: Catching Unsealed Packs at Line Speed",
     "sachet seal inspection AI India",
     ["computer-vision", "seal-inspection", "fmcg", "india"],
     "Spoke: unsealed-sachet detection on spice/nutrition/FMCG powder lines — the #1 recall "
     "trigger. How vision catches partial seals and channel leaks inline without slowing the "
     "line. India FMCG context (Unilever/ITC/Dabur-class sachet volumes). Links up to the pillar."),

    ("Fill-Level Inspection with Computer Vision: Stop Underfilled Packs Shipping",
     "fill level inspection computer vision India",
     ["computer-vision", "fill-level", "fmcg", "india"],
     "Spoke: underfill/overfill detection on bottling and pouch lines — legal-metrology risk "
     "plus giveaway cost. Vision vs checkweigher, when each wins, accuracy at line speed. "
     "Indian F&B / personal-care context. Links up to the pillar and across to seal + cap."),

    ("Missing-Cap and Closure Detection on Indian Bottling Lines with AI Vision",
     "cap inspection vision system India",
     ["computer-vision", "cap-inspection", "fmcg", "india"],
     "Spoke: missing/cocked-cap and closure-integrity detection on oil, beverage and personal-"
     "care bottling lines. Reject-timing and PLC integration reality on a real Indian line. "
     "Links up to the pillar and across to fill-level."),

    ("Date-Code and Batch-Code OCR Verification for FMCG Lines in India",
     "date code OCR inspection India",
     ["computer-vision", "ocr", "fmcg", "india"],
     "Spoke: date/batch/MRP print verification — the compliance defect that ships thousands of "
     "unreadable or wrong-date packs before anyone notices. Vision-OCR that reads inkjet/laser "
     "codes at speed; ties to Buteforce's dual-engine OCR work. Links up to the pillar."),

    ("Label Presence and Alignment Inspection: AI Vision for Multi-SKU FMCG Lines",
     "label inspection AI India FMCG",
     ["computer-vision", "label-inspection", "fmcg", "india"],
     "Spoke: missing / skewed / wrong-SKU label detection across fast-changing Indian FMCG SKUs. "
     "How the model generalises across variants without per-SKU retraining. Links up to the "
     "pillar and across to date-code + multi-SKU changeover."),

    ("Multi-SKU Changeover Inspection: One Vision System, Every Product Variant",
     "multi-SKU visual inspection India",
     ["computer-vision", "multi-sku", "manufacturing", "india"],
     "Spoke: the objection every Indian FMCG plant raises — 'we change SKUs hourly, vision "
     "can't keep up.' How a single system handles changeovers without re-teaching, and why "
     "custom beats a rigid platform here. Buyer-objection post. Links up to the pillar."),

    ("What FMCG Visual Inspection Costs in India (and What Actually Drives the Price)",
     "FMCG visual inspection system cost India",
     ["computer-vision", "cost", "fmcg", "india"],
     "Commercial spoke: honest India-specific cost of a line-inspection system — cameras, "
     "lighting, edge compute, integration, per-line vs per-plant. Highest buyer intent in the "
     "cluster; captures 'cost' searchers. Links up to the pillar and to the existing QC-cost post."),
]


def seed(dry_run: bool = False) -> None:
    print(f"Seeding {len(CLUSTER)} cluster-expansion topics" + (" (dry run)" if dry_run else "") + "...\n")
    if dry_run:
        for i, (title, kw, tags, _brief) in enumerate(CLUSTER, 1):
            print(f"  [{i:>2}] {slugify(title)}\n        kw: {kw}  tags: {', '.join(tags)}")
        print("\nDry run — nothing written.")
        return

    db = _db()
    now = datetime.utcnow().isoformat() + "Z"
    inserted = updated = 0

    for title, target_keyword, tags, brief in CLUSTER:
        slug = slugify(title)
        existing = db.table("topics").select("id,status").eq("slug", slug).limit(1).execute()

        if existing.data:
            row = existing.data[0]
            # Refresh metadata, but never rewind a topic already in flight.
            db.table("topics").update({
                "title": title,
                "tags": tags,
                "brief": brief,
                "target_keyword": target_keyword,
                "updated_at": now,
            }).eq("id", row["id"]).execute()
            print(f"  ~ refreshed: {slug} (status={row['status']})")
            updated += 1
            continue

        db.table("topics").insert({
            "slug": slug,
            "title": title,
            "status": "queued",
            "tags": tags,
            "brief": brief,
            "target_keyword": target_keyword,
            "created_at": now,
            "updated_at": now,
        }).execute()
        print(f"  + queued:    {slug}")
        inserted += 1

    print(f"\nDone. {inserted} queued, {updated} refreshed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the GSC-driven FMCG/CV cluster expansion")
    parser.add_argument("--dry-run", action="store_true", help="Print plan, write nothing")
    args = parser.parse_args()
    if not args.dry_run:
        try:
            from dotenv import load_dotenv
            load_dotenv(Path(__file__).resolve().parent / ".env")
        except Exception:
            pass
        if not os.environ.get("SUPABASE_URL"):
            print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_KEY not set in blog-agent/.env")
            sys.exit(1)
    seed(dry_run=args.dry_run)
