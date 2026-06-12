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

## Blog Swarm Pipeline Architecture

> Reality check (2026-06-08): the blog swarm lives in `Projects/Marketing agents/blog-agent/`.
> It is controlled by a **Next.js dashboard** (and `run.py` CLI), **not Telegram**. There is no
> DesignerAgent and no Telegram code in this tree. Lead outreach is a *separate* project
> (`Projects/Lead Outreacher/review_app`) — do not conflate the two.

```
Next.js dashboard (app/api/) or run.py CLI → BlogOrchestrator (Google ADK, stateful, Supabase state)
                              ↓
   queued → researching → verifying_research → writing → verifying_draft → publishing → published
                              ↓
   ┌──────────────────────────────────────────────────────────────────────┐
   │ Research → [VERIFY] → Writer → Humaniser → Imager → Linker → Schema    │
   │                         → [VERIFY] → Publisher                         │
   └──────────────────────────────────────────────────────────────────────┘
                              ↓
        Publish: POST MDX + JSON-LD to buteforce.com/api/agent/blog (site API, Bearer AGENT_SECRET_KEY)
```

Two human approval gates (research digest, draft) with a rejection → re-run-with-feedback loop.

### Key Files (Blog Swarm — `blog-agent/`)
- `swarm/orchestrator.py` — stateful BlogOrchestrator (Google ADK), Supabase state store
- `swarm/agents/` — `research.py`, `writer.py`, `humaniser.py`, `imager.py`, `linker.py`, `schema_ld.py`, `publisher.py`
- `swarm/agents/brand_context.py` — loads `config/positioning.md` (ICP), `config/seo-strategy.md` (keywords), brand bible
- `swarm/tools/` — `tavily_tool.py`, `youtube_tool.py`, `github_tool.py` (search + site-API publish), `site_tool.py`, `image_tool.py`, `supabase_tool.py`
- `config/positioning.md` + `config/seo-strategy.md` — **authoritative India-first ICP + keyword strategy**, repo-local, loaded by every agent
- `seed_topics.py` — seeds the 24-post India-first roadmap (`Buteforce_Marketing_Strategy_2026.md` §4) as Supabase topics
- `setup_db.py` — idempotent schema (topics, blog_posts, `brief`/`target_keyword`/`schema_json` columns, RLS)
- `dashboard/app/api/` — Next.js routes that spawn `python run.py`
- Supabase DB — `topics` + `blog_posts` state machine and artifacts
- `D:/Projects/Buteforce/.agents/knowledge/` — vault brand memory (secondary to repo-local `config/`)

---

## Email Domain Strategy
- **Primary domain** (`buteforce.com`) — PROTECTED. Never used for cold outreach.
- **Cold subdomain — DECIDED 2026-06-09:** cold sends from **`outreach.buteforce.com`** (own SPF/DKIM/DMARC, warmup 10→50/day over 4–6 wks). Keeps the brand name, isolates the root domain's inbound reputation.
- This protects primary domain reputation and deliverability for inbound leads
- Full autonomous engine spec → [[reach_engine]]

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
- [x] Google ADK blog swarm built — BlogOrchestrator + 6 agents (Research, Writer, Humaniser, Imager, Linker, Publisher) + JSON-LD schema step. Controlled via Next.js dashboard / `run.py` (NOT Telegram; no DesignerAgent).
- [x] **Engine realigned to India-first strategy (2026-06-08):** `config/positioning.md` + `config/seo-strategy.md` now drive Research/Writer; old US/UK/UAE/AU ICP line removed. 24-post roadmap seedable via `seed_topics.py`. Article + FAQ JSON-LD generated per post.
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
- [x] ~~`GITHUB_REPO` env var~~ — OBSOLETE. Publishing POSTs to the site API, not GitHub. Live publish needs `AGENT_SECRET_KEY` + `SITE_API_URL` set and `PUBLISH_DRY_RUN=false` (default is dry-run).
- [ ] LinkedIn Insight Tag (retargeting pixel) — add to layout.tsx head, 10 mins
- [ ] Clutch / DesignRush / G2 free agency listings — improves GEO + LLM citations
- [ ] Remove theme-toggle.tsx from nav — dark mode should be disabled per brand rule
- [ ] Fix layout.tsx default OG title — currently "AI Automation & Computer Vision", should be "Precision AI Systems"
- [ ] Create individual service landing pages: /services/computer-vision, /services/document-ai, /services/ai-agents
- [ ] Publish Blog Post #1 "Industrial AI for Chennai's Manufacturing Corridor" — seeded as a queued topic by `seed_topics.py`; run it through the swarm and flip `PUBLISH_DRY_RUN=false` once the URGENT site fixes are done
- [ ] Expand case study pages /work/[slug] with 300–500 word write-ups (currently thin content)

- [x] Tier 1 review UI built locally in `review_app/` for manual draft review and send flow
- [x] Migrate `review_app/generator.py` from Anthropic to Gemini Developer API so Tier 1 manual outreach can generate drafts without Anthropic credits

## Control Surface (Next.js dashboard / CLI — NOT Telegram)

> The Telegram control flow was never built in `blog-agent/`. Control is the dashboard or `run.py`.

- New topic → `POST /api/run` (or `python run.py --topic "..." --tags "..."`) starts research
- Approve a gate → `POST /api/approve` (or `python run.py --approve <slug>`) advances to the next stage
- Reject a gate → `POST /api/reject` with feedback (or `python run.py --reject <slug> --feedback "..."`) re-runs with feedback
- `GET /api/topics`, `GET /api/topic/:slug` — status + artifacts
