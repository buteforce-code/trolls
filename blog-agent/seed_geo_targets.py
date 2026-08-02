"""
Seed the AI-visibility (GEO) target batch — items 4-7 of the Track B content plan.

WHY THIS EXISTS
AI Visibility SCAN 001 (2026-07-26, `.agents/knowledge/ai_visibility.md`) measured Buteforce at
**0/18 recommended, 0/18 cited** across the frozen buyer-prompt set. Two of its structural
findings drive this batch:

  - Finding 1: in this category the pages AI cites are *vendor-owned listicles and comparison
    posts*, not neutral directories. Softlabs ranks itself #1 in its own "top computer vision
    companies in India" post. Publishing our own honest listicle is the category's proven move.
  - The winnable prompts are DECISION-SHAPED ones (P05, P09) where AI cites vendor comparison
    blogs rather than SaaS product pages.

Each topic below names the frozen prompt IDs it targets. Every post inherits the GEO template
enforced by `swarm/geo.py` — question-form H2s with self-contained answers, hard numbers from
`case_studies.md`, a competitor-inclusive comparison table, an explicit "not a fit if…" section,
a visible dateModified and a named author.

ORDERING
`autopilot._pick_next_queued` drains `status='queued'` ordered by `created_at` ASC, so priority is
expressed as a timestamp. These four are backdated to sort AHEAD of the eight FMCG cluster topics
seeded by `seed_cluster_expansion.py`, and ahead of each other in plan order. That is deliberate:
the FMCG page they were meant to support has now been rewritten directly, so the highest-ROI
remaining work is the AI-visibility batch. The cluster still runs, just behind this.

Same idempotent upsert-by-slug contract as the other seeders. Nothing publishes on seed — topics
land as `queued` and the autopilot 24h veto window still governs anything that ships.

Usage:
  python seed_geo_targets.py            # insert/refresh the batch
  python seed_geo_targets.py --dry-run  # print the plan, write nothing
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from swarm.slugs import slugify


def _db():
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv(Path(__file__).resolve().parent / ".env")
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


# Anchor for the backdated created_at values, spaced 1 minute apart to fix the internal order.
# Must be earlier than EVERY other queued topic. The original 24-post roadmap
# (`seed_topics.py`) is all stamped 2026-06-08T09:19, so a 2026-07 anchor put this batch at
# position 19 — measured, not assumed. 2026-06-01 puts it first.
_PRIORITY_ANCHOR = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

# prompts, title, target_keyword, tags, brief
TARGETS: list[tuple[str, str, str, list[str], str]] = [
    (
        "P01 / P04 / P17",
        "Top Computer Vision Companies for Manufacturing Quality Control in India (2026)",
        "computer vision companies manufacturing quality control India",
        ["computer-vision", "manufacturing", "india", "comparison"],
        "THE LISTICLE PLAY — the single highest-leverage post in this batch. SCAN 001 finding 1: "
        "this category's citation graph is vendor-owned listicles. Softlabs, NextBrain and "
        "jidoka-tech all rank by publishing their own 'top companies' post; AI cites those pages "
        "directly. So publish ours.\n"
        "NON-NEGOTIABLE — CREDIBILITY IS THE WHOLE MECHANISM: include real competitors and be "
        "genuinely useful about them. Cover Cognex, Keyence and Omron (global sensor vendors), "
        "Kritikal Solutions, Detect Technologies, Assert AI, Wobot.ai and Intello Labs (Indian "
        "CV firms), Optomech and Indus Vision (Indian machine-vision integrators), and Buteforce. "
        "For EACH entry give what they are actually best at and who should pick them. Do NOT rank "
        "Buteforce #1 — place it honestly as the custom-build option for defects no catalogue "
        "model was trained on, evidenced by 99.2% accuracy at 120 items/min and 94% error "
        "reduction. A listicle that crowns its own author is the thing readers and answer engines "
        "discount; the honesty IS the ranking strategy.\n"
        "Structure it as a real comparison table plus a short honest paragraph per company. Include "
        "a selection-criteria section (what to actually ask a vendor) and a 'not a fit' section "
        "covering when a listicle like this should be ignored entirely.",
    ),
    (
        "P09",
        "OCR vs Document AI: What Your Finance Team Actually Needs",
        "OCR vs document AI finance team",
        ["document-ai", "ocr", "finance-ops", "comparison"],
        "DECISION-SHAPED AND GENUINELY WINNABLE. SCAN 001 flagged P09 explicitly: AI already cites "
        "vendor *comparison* blogs here (Flowis, Rillion, Ascend, DocXtract, Turian), not product "
        "pages — so a real comparison post can win the citation without any domain authority.\n"
        "The distinction to make sharply: OCR converts pixels to characters; document AI "
        "understands what a document IS and extracts fields with validation, confidence scores and "
        "exception routing. Most finance teams asking for 'OCR' need the second thing and do not "
        "know the term. Make that the spine.\n"
        "Compare honestly: Tesseract/plain OCR, cloud APIs (Google Document AI, AWS Textract, "
        "Azure Document Intelligence), SaaS platforms (Nanonets, Rossum, KlearStack), and a "
        "custom pipeline. Say where each wins — cloud APIs win on standard invoices and time to "
        "first result; SaaS wins when per-document pricing is acceptable forever; custom wins on "
        "mixed handwritten/printed, merged-cell tables and validation logic. Evidence: Buteforce's "
        "dual-engine OCR (Mistral 7B + Google Cloud Vision) returns sub-second latency on printed, "
        "handwritten and merged-cell-table documents. Include an accuracy-maths section: why 95% "
        "field accuracy still means a human touches most multi-field documents. India-first: GST "
        "invoices, e-way bills, handwritten challans, vernacular text.",
    ),
    (
        "P05",
        "Build vs Buy: Should You Build an AI Quality Control System or Buy One?",
        "build vs buy AI quality control system",
        ["computer-vision", "manufacturing", "build-vs-buy", "comparison"],
        "SAME DECISION SHAPE AS THE OCR POST — SCAN 001 shows P05's citation surface is consultancy "
        "and vendor blogs (parsec, agmis, dac.digital), all winnable with a better-evidenced post.\n"
        "Give the reader a real decision framework, not a pitch: total cost of ownership over three "
        "years, who owns the model weights, what happens when the product changes, how long each "
        "path takes to first production run, and what breaks in each. Buy = Cognex/Keyence sensors "
        "or a vision SaaS: faster, proven reliability, licence forever, limited to what the "
        "catalogue model was trained on. Build in-house = ₹18-40 lakh/yr per ML engineer and 3-12 "
        "months to production, right only if vision is core to the product long-term. Commission a "
        "custom build = fixed price, you own the weights, 4-8 weeks, right when the defect is "
        "specific to your line.\n"
        "Be explicit that BUY is the correct answer for standard inspections (presence, barcode, "
        "dimensional) — conceding that is what makes the rest credible. Evidence for the custom "
        "path: 99.2% accuracy at 120 items/min, 94% error reduction in month one. Include the "
        "failure mode nobody quotes: false positives that stop the line and get the system "
        "switched off. India-first: import duty and lead time on sensor hardware, local support "
        "reality, availability of ML hires in Chennai/Bangalore.",
    ),
    (
        "P10 / P11",
        "AI Agents for Real Estate Enquiries: What 70% Autonomous Handling Looks Like",
        "AI agent real estate enquiries qualify leads",
        ["ai-agents", "real-estate", "lead-qualification", "india"],
        "Targets both P10 (buyers wanting an agent to handle and qualify enquiries) and P11 (buyers "
        "shopping for real-estate chatbot *companies* — where SCAN 001 found three vendor-owned "
        "listicles ranking: streebo.com, svermo.ai, rybo.ai). So this post must work as a "
        "how-it-works piece AND carry a competitor comparison strong enough to answer P11.\n"
        "Lead with the delivered result, honestly scoped: a Buteforce real-estate agent handles 70% "
        "of property enquiries autonomously with 95% faster lead response and 24/7 availability, "
        "CRM-integrated. Be precise about what the other 30% is and why a human should take it — "
        "that boundary is the most useful thing in the post and the least written about.\n"
        "Compare honestly against ManyChat and generic chatbot builders (cheap, script-based, "
        "cannot qualify), Botpress and ORAI (real NLP platforms, per-seat cost, generic property "
        "logic), Crescendo and the P11 listicle vendors, and a custom agent. Cover the actual "
        "mechanics: budget/location/amenity qualification, viewing scheduling, neighbourhood "
        "questions, WhatsApp as the real channel in India, CRM write-back, and escalation rules. "
        "'Not a fit if' should be blunt: small agencies with low enquiry volume, anyone wanting the "
        "agent to close rather than qualify, and firms with no CRM to write into.",
    ),
]


# ── Repoints ─────────────────────────────────────────────────────────────────
# Topics whose original angle now collides with a hand-built site page. Publishing two pages
# against one query splits the ranking signal, and the geo *page* is the asset that wins P15 —
# SCAN 001's whole finding was that competitors beat us by having a location page, not a post.
# So the post is repointed to an adjacent intent and told to link up to the page.
REPOINTS: list[tuple[str, str, str, str]] = [
    (
        "ai-automation-company-in-chennai-what-we-build-and-why-it-sh",
        "How to Choose an AI Automation Partner in Chennai: 9 Questions to Ask",
        "how to choose AI automation company Chennai",
        "REPOINTED 2026-07-26 — the original angle ('About + services in blog form', keyword "
        "'AI automation company Chennai') now duplicates the hand-built geo landing page at "
        "/ai-automation-company-in-chennai. Two pages on one query cannibalise each other.\n"
        "New intent is vendor EVALUATION, not vendor discovery — a different search and a "
        "different buyer moment. Give the reader the nine questions that actually separate a "
        "vendor who will ship from one who will not: who owns the model weights and source code, "
        "what accuracy number goes in the contract and how it is measured, what the false-positive "
        "rate is, who collects the training images, what happens when the product changes, what "
        "the handover contains, whether hardware is marked up, what the timeline commitment is, "
        "and who owns the system internally after go-live.\n"
        "Answer each question with what a good answer sounds like AND what a bad one sounds like. "
        "Link UP to /ai-automation-company-in-chennai as the local-vendor page and to /pricing. "
        "Evidence: 99.2% accuracy at 120 items/min, 94% error reduction, 2-8 week delivery. "
        "'Not a fit if' should say plainly when the reader should not hire any agency at all.",
    ),
]


def _apply_repoints(db, now: str) -> int:
    """Re-aim topics whose original angle collides with a site page. Skips anything in flight."""
    changed = 0
    for slug, title, keyword, brief in REPOINTS:
        row = (db.table("topics").select("id,status").eq("slug", slug).limit(1).execute().data or [])
        if not row:
            print(f"  ! repoint target not found, skipping: {slug}")
            continue
        if row[0]["status"] != "queued":
            print(f"  ! {slug} is '{row[0]['status']}', not queued — leaving it alone")
            continue
        db.table("topics").update({
            "title": title, "target_keyword": keyword, "brief": brief, "updated_at": now,
        }).eq("id", row[0]["id"]).execute()
        print(f"  ↻ repointed: {slug}\n      → {title}")
        changed += 1
    return changed


def seed(dry_run: bool = False) -> None:
    print(f"Seeding {len(TARGETS)} GEO target topics" + (" (dry run)" if dry_run else "") + "...\n")

    if dry_run:
        for i, (prompts, title, kw, tags, _brief) in enumerate(TARGETS, 1):
            created = _PRIORITY_ANCHOR + timedelta(minutes=i)
            print(f"  [{i}] {slugify(title)}")
            print(f"      prompts : {prompts}")
            print(f"      keyword : {kw}")
            print(f"      tags    : {', '.join(tags)}")
            print(f"      priority: created_at={created.isoformat()} (drains #{i})\n")
        for slug, title, keyword, _brief in REPOINTS:
            print(f"  ↻ repoint {slug}\n      → {title}\n      keyword: {keyword}\n")
        print("Dry run — nothing written.")
        return

    db = _db()
    now = datetime.now(timezone.utc).isoformat()
    inserted = updated = 0

    for i, (prompts, title, target_keyword, tags, brief) in enumerate(TARGETS, 1):
        slug = slugify(title)
        created_at = (_PRIORITY_ANCHOR + timedelta(minutes=i)).isoformat()
        brief_with_prompts = f"[AI-visibility target: {prompts}]\n{brief}"

        existing = db.table("topics").select("id,status").eq("slug", slug).limit(1).execute()

        if existing.data:
            row = existing.data[0]
            # Refresh metadata and re-assert priority, but never rewind a topic already in flight.
            db.table("topics").update({
                "title": title,
                "tags": tags,
                "brief": brief_with_prompts,
                "target_keyword": target_keyword,
                "created_at": created_at,
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
            "brief": brief_with_prompts,
            "target_keyword": target_keyword,
            "created_at": created_at,
            "updated_at": now,
        }).execute()
        print(f"  + queued #{i}: {slug}")
        inserted += 1

    repointed = _apply_repoints(db, now)

    print(f"\nDone. {inserted} queued, {updated} refreshed, {repointed} repointed.")
    print("These drain ahead of the FMCG cluster batch. Autopilot writes one per tick and holds "
          "each for the 24h veto window before publishing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the AI-visibility (GEO) target batch")
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
