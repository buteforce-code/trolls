---
links: "[[INDEX]] | [[dhyan_psychology]] | [[founder]] | [[brand_bible]] | [[tech_stack]]"
type: operations
last-updated: 2026-04-22
---

# Marketing Engine — Buteforce Lead Generation System

> Zero-budget constraint. All decisions here respect [[dhyan_psychology#Decision Making Principles]].
> Lead identity and voice rules: [[founder]] and [[brand_bible#Manifesto]].

## Budget Constraint
**Zero budget for Months 1–3.** All outreach must be zero-to-minimal cost. No paid ads, no premium tools.
**Phased paid plan (Month 4+):** Google Search Ads first ($300–500/month), LinkedIn retargeting second ($300/month once pixel audience reaches 300+). Skip Meta ads — wrong audience for B2B AI services.

---

## Lead Sources

### 1. Upwork (Primary)
- Dhyan has manually scraped Upwork client data into a CSV (`Name sheet - Clients data.csv`)
- The CSV contains: company name, contact info, project history, estimated budget
- High-value signals: clients who have hired for AI/ML work before = pre-qualified buyers
- See [[founder#Professional Background]] for Dhyan's Upwork profile context

### 2. Organic SEO (Mid-term)
- buteforce.com is being optimized for AI agency keywords
- GEO (Generative Engine Optimization) implemented — structured data for LLM discovery
- `robots.txt`, `llms.txt`, JSON-LD structured data all in place
- ⚠️ CRITICAL: buteforce.com is NOT indexed by Google as of 2026-04-15. Submit to Google Search Console immediately.
- See [[tech_stack]] for implementation details

### 3. LinkedIn Personal Brand (Active — Dhyan's profile @dhyankarthik)
- Post from personal profile ONLY — company pages get 5% feed allocation vs 65% for personal
- 3–4x per week: Mon (text/story), Wed (carousel), Fri (question/engagement)
- External links go in FIRST COMMENT only — in-post links reduce reach by 40% (2026 algo)
- Carousels average 6.60% engagement rate — highest organic format on platform
- See [[content_calendar#LinkedIn Posting Cadence]] for schedule

### 4. X (Twitter) — Active
- 5 posts/week — technical threads + short punchy observations
- Target audience: CTOs, ops directors, technical founders in manufacturing/logistics/finance
- Threads perform best: architecture breakdowns, case study walkthroughs, build diaries
- External links are fine in-post on X (unlike LinkedIn)

### 5. Warm Network
- LinkedIn profile (dhyankarthik) — direct DMs to qualified connections

---

## Outreach Pipeline Architecture

```
Telegram / Website → SwarmOrchestrator (Google ADK)
                              ↓
            ┌─────────────────────────────────────┐
            │  ResearchAgent → [VERIFY with Dhyan] │
            │  WriterAgent   → [VERIFY with Dhyan] │
            │  HumaniserAgent (brand voice filter)  │
            │  DesignerAgent → [VERIFY with Dhyan]  │
            └─────────────────────────────────────┘
                              ↓
                   Auto-publish to buteforce.com (MDX via GitHub API)
```

### Key Files (Marketing Swarm)
- `scripts/ingest_leads.py` — bridges `leads_clean.csv` into Supabase (154 leads ingested)
- `swarm/orchestrator.py` — Superior Orchestrating Agent (Google ADK, stateful)
- `swarm/sub_agents.py` — ResearchAgent, WriterAgent, HumaniserAgent, DesignerAgent
- `dashboard/lib/telegram-orchestrator-bridge.ts` — Next.js → Python bridge
- `dashboard/app/api/telegram/webhook/route.ts` — Telegram webhook entry point
- Supabase DB — stores full campaign state machine, artifacts, messages
- `config/brand-bible.md` + `D:/Projects/Buteforce/.agents/knowledge/` — static brand memory loaded by all agents

---

## Email Domain Strategy
- **Primary domain** (`buteforce.com`) — PROTECTED. Never used for cold outreach.
- **Warm-up domain** — separate subdomain or cheap alternate domain for cold campaigns
- This protects primary domain reputation and deliverability for inbound leads

---

## Campaign Rules
1. Personalization is mandatory — no spray-and-pray
2. Reference their actual project history from the scraped data
3. Lead with the problem, not the company
4. Always include a verifiable proof point (case study metric or client name) → [[brand_bible#Manifesto]]
5. Max 3 follow-ups per lead before marking as cold

---

## Tier 1 Manual Outreach

- High-value Tier 1 leads are handled in a local manual review tool at `Projects/Lead Outreacher/review_app`.
- Flow: select lead -> generate draft -> edit subject/body -> approve and send -> sync back to `outreach_tracker.csv`.
- Leads with no email stay blocked in the UI until enrichment is completed.
- `review_app` now generates drafts through Gemini Developer API with `gemini-2.5-pro` as the quality-first default model.
- Remaining blocker as of 2026-04-22: SMTP send still requires `SMTP_PASS` in `review_app/.env`.

---

## Current Status (April 2026)
- [x] Lead database populated in Supabase — 154 Upwork leads ingested as `intake` campaigns
- [x] Google ADK swarm built — Orchestrator + 4 sub-agents (Research, Writer, Humaniser, Designer)
- [x] Telegram webhook wired to SwarmOrchestrator (ADK, Vertex AI via GCP billing active)
- [x] End-to-end test verified: research→draft→image→publish pipeline confirmed working
- [x] Obsidian vault loaded as static brand memory by all swarm agents
- [x] GCP billing enabled (₹1,000 credit, Vertex AI active, gemini-2.0-flash)
- [x] Full marketing strategy compiled (2026-04-15) → `Marketing/buteforce_marketing_strategy_2026.md`
- [x] Full CMO audit completed (2026-04-18) → `Buteforce Marketing/buteforce_full_audit_q2_2026.md`
- [x] Google Search Console property connected — confirmed via screenshot 2026-04-18
- [ ] **URGENT #1: Submit sitemap + request manual indexing in GSC — 1 impression in 3 months (brand query only). Go to GSC → Sitemaps → submit buteforce.com/sitemap.xml → then URL Inspection each key page → Request Indexing**
- [ ] **URGENT #2: Fix hero section dark mode violation — entire site confirmed dark (hero.tsx bg-black). brand rule is light-always since 2026-04-12. Not yet implemented in codebase.**
- [ ] **URGENT #3: Add keyword H2 below hero H1 — H1 has zero SEO keywords**
- [ ] LinkedIn/Buffer publish credentials still needed for social channels
- [ ] `GITHUB_REPO` env var needs the real repo slug for live blog publishing
- [ ] LinkedIn Insight Tag (retargeting pixel) — add to layout.tsx head, 10 mins
- [ ] Clutch / DesignRush / G2 free agency listings — improves GEO + LLM citations
- [ ] Remove theme-toggle.tsx from nav — dark mode should be disabled per brand rule
- [ ] Fix layout.tsx default OG title — currently "AI Automation & Computer Vision", should be "Precision AI Systems"
- [ ] Create individual service landing pages: /services/computer-vision, /services/document-ai, /services/ai-agents
- [ ] Publish Blog Post #1 (written, needs MDX format + GITHUB_REPO env var)
- [ ] Expand case study pages /work/[slug] with 300–500 word write-ups (currently thin content)

- [x] Tier 1 review UI built locally in `review_app/` for manual draft review and send flow
- [x] Migrate `review_app/generator.py` from Anthropic to Gemini Developer API so Tier 1 manual outreach can generate drafts without Anthropic credits

## Telegram Control Commands
- Send any **topic** → Orchestrator starts the full pipeline
- Reply **APPROVE** → advances to next stage
- Reply **REJECT [feedback]** → triggers revision with feedback
- `/status` `/campaigns` `/drafts` `/topics` — dashboard commands
