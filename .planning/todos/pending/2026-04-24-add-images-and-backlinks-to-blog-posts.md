---
created: 2026-04-24T17:23
title: Add images and backlinks to blog posts
area: blog-agent
files:
  - blog-agent/
---

## Problem

Blog posts currently publish as plain MDX with no images and no contextual backlinks. Two gaps:

1. **Images (1–3 per post):** Every post needs a hero thumbnail (mandatory) plus 0–2 inline images based on topic — categories include blog thumbnail, architecture explanation diagrams, and topic-relevant illustrations. Zero-error tolerance: NO spelling mistakes, garbled text, or broken icons in any generated image.

2. **Backlinks:** Posts need contextual internal links back to buteforce.com (service pages, other blog posts) and authoritative external sources. Link placement must be natural, not stuffed.

Key constraint: No image model today guarantees 100% text accuracy (~6% failure rate on Nano Banana Pro, ~10% on others), so a QA vision gate is required to enforce zero-error policy.

## Solution

**Tiered image approach:**
- Hero/thumbnail → Imagen 4 or Nano Banana 2 via Vertex AI (text-free prompts to avoid mangling)
- Architecture/flow diagrams → Mermaid code rendered to SVG (zero spelling errors by construction, no weird icons)
- Conceptual inline illustrations → Imagen 4, text-free

**QA gate:** After every AI image generation, feed back into Gemini Vision with: "List every text string in this image. Flag any misspelled, garbled, or broken characters. Return JSON." If any flag → regenerate (max 3 retries) → fallback to text-free or Mermaid block.

**LinkerAgent:** Runs after humanise step; reads MDX + published posts + brand data; injects 2–4 links (1–2 internal to /services/* or /blog/*, 1–2 external). Rules: max 1 link per paragraph, descriptive anchor text.

**Pre-implementation confirmations needed:**
- GCP: Vertex AI enabled? GCS bucket for image hosting? Service-account key available?
- Mermaid rendering: OK to add @mermaid-js/mermaid component to Next.js site repo?
- Link budget: 2–4 links per post confirmed?
- Image count policy: 1 mandatory hero + 0–2 inline confirmed?

**Research sources (April 2026):**
- Nano Banana Pro 94% text accuracy — postquick.ai
- Mermaid for architecture diagrams (zero-error) — dev.to
- Internal linking best practice 2–5 per 1k words — Upward Engine
