# FMCG Post — Rescue Plan (the money page)

**Post:** `computer-vision-for-fmcg-manufacturing-in-india-what-unileve`
**Live:** https://www.buteforce.com/blog/computer-vision-for-fmcg-manufacturing-in-india-what-unileve
**Why it matters:** ~60% of all search visibility. Stuck on **page 2**. Converts nothing.

## What's wrong (diagnosis)

1. **Title is a buzzword, not a keyword.** Current: *"AI-Driven Quality Control: Revolutionizing
   FMCG Manufacturing in India"* — leads with "AI-Driven" / "Revolutionizing", not with what
   buyers search. Google has nothing clean to rank; users have nothing specific to click.
2. **Meta is filler.** Current opens *"Explore how…"* — no number, no defect, no CTA.
3. **The real anchor: the post is only ~650–700 words** — roughly half the engine's own 1,100-word
   floor. It predates the length gate. Title/meta alone will lift CTR but a thin page will not
   hold page 1 against Optomech / Indus Vision / iFactory, who have depth. **Body must be expanded.**

## Phase 1 — Quick win (title + meta), ship today

**New title** (58 chars, keyword-first, year for CTR):
```
Computer Vision for FMCG Quality Inspection in India (2026)
```
_Alt:_ `Computer Vision Quality Inspection for FMCG Lines in India`

**New meta description** (~153 chars, defect + throughput + accuracy + implicit CTA):
```
Computer-vision inspection catches seal, fill and label defects on Indian FMCG lines at 120 packs/min — 99.2% accuracy. See how it works and what it costs.
```

**Ship it:** re-POST the same slug to the site API (it upserts by slug) with the new title +
updated MDX frontmatter (`title:` and `description:`), or edit the post on the live site.

## Phase 2 — Depth pass (this week), what actually holds page 1

Expand to 1,400–2,000 words by adding defect-level H2s that match real buyer search:

- Seal / sachet integrity inspection
- Fill-level (underfill/overfill) inspection
- Cap / closure detection
- Date-code / batch-code OCR verification
- Label presence & alignment (multi-SKU)
- Line-speed & accuracy reality (120 CPM, 99.2%) + edge deployment
- What it costs in India

Then **interlink**: link this page **up** to the new FMCG pillar
(`computer-vision-inspection-fmcg-packaging-lines-india-2026`) and **across** to each defect
spoke seeded in `seed_cluster_expansion.py`. A page-2 page rises fastest when a fresh cluster of
internal links points at it.

Mechanism: re-run this topic through the (now length-gated) writer with a feedback brief, review
the draft, then publish. The whole defect cluster is already queued to supply those internal links.
