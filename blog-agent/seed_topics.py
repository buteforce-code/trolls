"""
Seed the 24-post India-first blog roadmap into Supabase as queued topics.

Source of truth: Buteforce_Marketing_Strategy_2026.md (Section 4 — 90-day roadmap).
Each topic carries its target keyword and a one-paragraph brief (the intended angle)
so the Research agent executes the strategy instead of researching blind.

Idempotent: re-running updates title/tags/brief/target_keyword for existing slugs
(matched by slug) and never resets a topic that has already moved past `queued`.

Usage:
  python seed_topics.py            # insert/refresh all 24 topics
  python seed_topics.py --dry-run  # print what would be seeded, touch nothing
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

def _db():
    # Lazy imports so the ROADMAP can be imported (e.g. for codegen / --dry-run)
    # without supabase/dotenv installed.
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv(Path(__file__).resolve().parent / ".env")
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _slugify(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:60]


# title, target_keyword, tags, brief(angle)
ROADMAP: list[tuple[str, str, list[str], str]] = [
    # ── Month 1 — fix the silence, plant flags ────────────────────────────────
    ("Industrial AI for Chennai's Manufacturing Corridor: What's Possible in 2026",
     "industrial AI Chennai",
     ["industrial-ai", "chennai", "manufacturing", "tamil-nadu"],
     "Flagship positioning post. The Chennai manufacturing cluster (Hyundai/Sriperumbudur, Michelin, "
     "Nissan-Renault/Oragadam, BMW/Chennai) and what AI actually solves on those floors. Claim the "
     "'Industrial AI company for Chennai's corridor' narrative no competitor has taken."),

    ("Computer Vision Quality Control in Indian Manufacturing: The Complete 2026 Guide",
     "computer vision quality control India",
     ["computer-vision", "quality-control", "manufacturing", "india"],
     "Pillar post for Cluster A, 2,500+ words. Deep, practical guide to deploying CV-based visual "
     "inspection on Indian production lines — data, lighting, throughput, accuracy, edge deployment."),

    ("How We Deployed Computer Vision on an Orthopedic Manufacturing Line (Full Case Study)",
     "manufacturing defect detection AI",
     ["case-study", "computer-vision", "manufacturing", "defect-detection"],
     "Expand the orthopedic insole classifier work page into a full case study: the problem, zero "
     "ground-truth start, what broke first, results (99.2% accuracy, 120/min). Outcomes, not promises."),

    ("AI Automation Company vs. AI Platform: Which Is Right for Your Factory?",
     "AI automation for manufacturing India",
     ["ai-automation", "manufacturing", "india", "custom-vs-platform"],
     "Position Buteforce (custom builder) directly against SwitchOn/Assert AI platform plays. Why a "
     "custom production system beats a dashboard subscription for a real Indian factory."),

    ("Retail Footfall Analytics India 2026: Turn Your CCTV Into Business Intelligence",
     "retail footfall analytics India",
     ["retail-analytics", "footfall", "hooter", "india"],
     "Build on the foot-traffic post, go deeper on India retail context. Existing CCTV → zone analytics, "
     "dwell, missed-sale signals without expensive new hardware (Hooter value prop, unbranded)."),

    ("The SITAC Effect: What India's New AI Corridors Mean for Manufacturing Startups",
     "SITAC India Sweden AI startup",
     ["sitac", "india-sweden", "bilateral", "policy"],
     "Macro-trend post that officials share. Explain the India-Sweden SITAC corridor and what an Indian "
     "manufacturing-AI startup needs to participate. Companion: sitac_india_sweden_opportunity.md."),

    ("AI Automation Company in Chennai: What We Build and Why It Ships",
     "AI automation company Chennai",
     ["ai-automation", "chennai", "positioning", "local-seo"],
     "About + services in blog form. Pure local-SEO positioning for 'AI automation company Chennai' "
     "(zero competition). What we build, how we ship, why custom beats platform."),

    ("n8n vs. Python for AI Workflow Automation: A Production Engineer's Honest Take",
     "n8n automation agency India",
     ["n8n", "python", "automation", "engineering"],
     "Technical opinion piece for engineers (LinkedIn/Upwork shares). When n8n is enough and when you "
     "need real Python in production — from someone who ships both for Indian clients."),

    # ── Month 2 — build authority, go deep ────────────────────────────────────
    ("What Does a Computer Vision System Actually Cost? 2026 India Market Reality",
     "computer vision QC system cost",
     ["computer-vision", "cost", "india", "manufacturing"],
     "Companion to the April cost post with India-specific pricing reality. Hardware, integration, "
     "edge vs cloud, ongoing cost — honest numbers, no vendor fog."),

    ("Retail Zone Analytics: How AI Cameras Find the Dead Zones in Your Store",
     "retail zone analytics India",
     ["retail-analytics", "zone-analytics", "hooter", "india"],
     "Educational Hooter content without naming Hooter. How zone/heatmap analytics from existing cameras "
     "surface dead zones and lost revenue for Indian multi-location retail."),

    ("Why Sandvik, ABB, and Volvo Need Local AI Partners in India (And What That Looks Like)",
     "Sweden India manufacturing AI",
     ["bilateral", "india-sweden", "manufacturing", "ai-partners"],
     "Map Swedish industrial companies operating in India to the AI use cases Buteforce solves. "
     "Bilateral-corridor visibility play; gets shared in India-Sweden business circles."),

    ("Custom AI Agent Development India: What to Ask Before You Hire",
     "custom AI agent development India",
     ["ai-agents", "india", "buyer-guide", "hiring"],
     "Buyer guide that positions Buteforce as the right answer. The questions an Indian ops/CTO buyer "
     "should ask before commissioning a custom AI agent — and the red flags."),

    ("Document AI vs. Traditional OCR: Why We Use Both (And When)",
     "document AI extraction service India",
     ["document-ai", "ocr", "india", "automation"],
     "When classic OCR is enough vs when you need document AI / vision LLMs. Buteforce's dual-engine "
     "routing (Mistral Vision + OCR) for handwritten/structured Indian documents."),

    ("Missed Sale Detection: How Retail AI Spots Revenue You're Leaving on the Floor",
     "missed sale detection retail AI",
     ["retail-analytics", "missed-sale", "hooter", "india"],
     "Hooter's core value as a blog post. How camera AI detects queue abandonment, stockout walk-aways, "
     "and unserved customers — quantified revenue recovery for Indian retail."),

    ("How Hyundai's India Manufacturing Expansion Creates AI Opportunities for Chennai Startups",
     "India Korea Digital Bridge",
     ["hyundai", "chennai", "bilateral", "india-korea"],
     "Chennai angle on the Sriperumbudur plant + India-Korea Digital Bridge. The AI opportunities a "
     "Korean OEM expansion opens for local Chennai AI builders. Shared in Korea-India circles."),

    ("The Real ROI of AI in Manufacturing: Numbers from 10 Production Deployments",
     "AI manufacturing ROI India",
     ["roi", "manufacturing", "india", "case-data"],
     "Most shareable post in the plan. Aggregate real numbers across Buteforce's 10+ deployments — "
     "accuracy, throughput, time saved, payback — for Indian manufacturing ROI."),

    # ── Month 3 — multiply, repurpose, compound ───────────────────────────────
    ("AI Automation for SME Manufacturers in India: A Realistic Getting-Started Guide",
     "AI automation manufacturing India SME",
     ["ai-automation", "sme", "manufacturing", "india"],
     "Realistic, no-hype starting guide for Indian SME manufacturers. Where to start, what one line to "
     "automate first, budget reality, how to avoid building the wrong thing correctly."),

    ("Why We Build on Edge (Not Cloud) for Manufacturing AI",
     "edge AI manufacturing India",
     ["edge-ai", "manufacturing", "india", "engineering"],
     "Technical depth post for an engineering audience. Latency, bandwidth, factory-floor reality, and "
     "data-sovereignty reasons Buteforce deploys on edge for Indian manufacturing."),

    ("IndiaAI Mission + Chennai Manufacturing = The Opportunity Nobody Is Talking About",
     "IndiaAI startup program",
     ["indiaai", "chennai", "ecosystem", "policy"],
     "Ecosystem post connecting the IndiaAI Mission to the Chennai manufacturing base. The under-discussed "
     "opportunity at that intersection; gets seen by NASSCOM / IndiaAI officials."),

    ("Computer Vision for FMCG Manufacturing in India: What Unilever, ITC, and Nestlé Are Solving",
     "computer vision FMCG India manufacturing",
     ["computer-vision", "fmcg", "manufacturing", "india"],
     "CV use cases specific to Indian FMCG lines (packaging, label, fill, date-code inspection) with "
     "named industry context. High commercial intent for FMCG quality leaders."),

    ("Footfall vs. Conversion: Why Counting Customers Isn't Enough",
     "retail analytics India store performance",
     ["retail-analytics", "conversion", "hooter", "india"],
     "Move retail buyers past vanity footfall counts to conversion and zone performance. What Indian "
     "store operators should actually measure — and how camera AI gets them there."),

    ("How to Write a Brief for an AI Automation Project (Template + Examples)",
     "AI automation project brief India",
     ["ai-automation", "template", "lead-magnet", "india"],
     "Highest-conversion lead-magnet post. A reusable brief template + worked examples so an Indian buyer "
     "can spec an AI automation project well — and naturally hand it to Buteforce."),

    ("3 Real Computer Vision Case Studies from Indian Manufacturing (Outcomes, Not Promises)",
     "computer vision case study manufacturing India",
     ["case-study", "computer-vision", "manufacturing", "india"],
     "Aggregate all three manufacturing case studies into one SEO post. Problem → approach → measured "
     "outcome for each. Proof-heavy, high commercial intent."),

    ("The Chennai AI Ecosystem in 2026: Why This Is Where Industrial AI Gets Built",
     "Chennai AI ecosystem",
     ["chennai", "ecosystem", "industrial-ai", "narrative"],
     "Quarterly narrative + linking-hub post. Why Chennai is where industrial AI gets built (talent, "
     "manufacturing base, bilateral corridors). Links to everything; big-picture positioning."),
]


def seed(dry_run: bool = False) -> None:
    print(f"Seeding {len(ROADMAP)} roadmap topics" + (" (dry run)" if dry_run else "") + "...\n")
    if dry_run:
        for i, (title, kw, tags, _brief) in enumerate(ROADMAP, 1):
            print(f"  [{i:>2}] {_slugify(title)}\n        kw: {kw}  tags: {', '.join(tags)}")
        print("\nDry run — nothing written.")
        return

    db = _db()
    now = datetime.utcnow().isoformat() + "Z"
    inserted = updated = skipped = 0

    for title, target_keyword, tags, brief in ROADMAP:
        slug = _slugify(title)
        existing = db.table("topics").select("id,status").eq("slug", slug).limit(1).execute()

        if existing.data:
            row = existing.data[0]
            # Refresh metadata, but never rewind a topic that's already in flight.
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

    print(f"\nDone. {inserted} queued, {updated} refreshed, {skipped} skipped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the 24-post India-first roadmap")
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
