---
links: "[[INDEX]] | [[marketing_engine]] | [[icp]] | [[outreach_templates]] | [[brand_bible]] | [[tech_stack]] | [[case_studies]]"
type: operations
last-updated: 2026-06-09
---

# Reach Engine — Buteforce Autonomous Lead Engine

> Greenfield successor to the manual Tier-1 Lead Outreacher (`Projects/Lead Outreacher/review_app`).
> Goal: scrape → segment → research → personalize → send → follow-up → book-consult, with the
> Obsidian vault as living memory. Zero-budget constraint per [[marketing_engine#Budget Constraint]].
> Voice/anti-patterns: [[brand_bible#Anti-Patterns Never Do This]]. Proof points: [[case_studies]].

---

## 0. Spec Lock (decisions made 2026-06-09 with Dhyan)

| Decision | Choice | Why it matters |
|---|---|---|
| Build approach | **Greenfield rebuild**, lift proven modules from `review_app` (`mailer.py`, `inbox_checker.py`, email template) | Clean architecture; don't throw away the working SMTP/IMAP/Gemini pieces |
| Target market | **India-local SMBs**, Chennai/TN first | Redefines ICP away from the old US/UK/UAE/AU enterprise line → see §7 + [[icp]] addendum |
| Verticals (phase order) | **Import/Export + Logistics FIRST**, then Clinics + Retail, then all-India | B2B trade firms publish email; clinics/retail are phone-heavy (proven in sample, §8) |
| Offer | Existing custom AI systems (CV, Document AI/OCR, AI agents) **+ free audit → custom scope** | No new productization required to start; audit is the universal CTA |
| Channel | **Email only (for now)**; WhatsApp is a later phase | Keeps phase 1 compliant + simple; phone-only leads are parked |
| Sending domain | **Subdomain `outreach.buteforce.com`** with its own SPF/DKIM/DMARC | Protects primary `buteforce.com` inbound reputation ([[marketing_engine#Email Domain Strategy]]) |
| Autonomy | **Auto-send with throttling + human spot-check + all replies reviewed** | Volume without a per-email gate; guardrails carry the brand-safety load (§6) |
| Stack | **Google Sheets = DB + UI**, Python scripts, Gemini (AI Studio) for research + drafting | Dead simple, matches what Dhyan already runs; Sheets is the human surface |
| Volume | **30–50/day steady-state**, slow warmup ramp | Safe for a brand-new subdomain + a one-person consult pipeline |
| Consult booking | **Cal.com/Calendly link auto-sent on `interested`/`meeting_requested`**, Dhyan runs the call | Reuses the existing IMAP reply-classifier labels |
| Memory | **Obsidian vault** (`.agents/`) read at start, updated at end of every run | This file is the engine's source of truth |

---

## 1. System Overview

```
                         ┌─────────────────────────────────────────────┐
                         │  Obsidian vault (.agents/) — MEMORY          │
                         │  read at start · write at end of every run   │
                         └───────────────▲───────────────┬─────────────┘
                                         │ retrieve       │ update
 [1 DISCOVER]   [2 ENRICH/DEDUP]   [3 SEGMENT]   [4 RESEARCH]   [5 DRAFT]   [6 SEND]   [7 FOLLOW-UP]   [8 REPLY]   [9 CONSULT]
   scrape free  →  clean + email  →  tier A/B/C →  per-lead    →  Gemini   →  SMTP    →  3-step seq   →  IMAP +   →  Cal link
   directories     verify, dedup     by ICP fit    dossier        on-brand    outreach.   throttled       Gemini      auto-send
        │              │                │             │             email      buteforce   30–50/day       classify    on interest
        └──────────────┴────────────────┴─────────────┴─────────────┴───────────┴───────────┴───────────────┴────────────┘
                                         ▼
                        Google Sheet (DB + human spot-check UI)
```

Source of truth = **one Google Sheet** with tabs: `Leads` (master), `Queue` (today's sends), `Sent`, `Replies`, `Booked`, `Suppression` (unsubscribes/bounces), `Config`. Python reads/writes via the existing service account (`friday@buteforce.iam.gserviceaccount.com`).

---

## 2. Lead Schema (Google Sheet `Leads` tab)

`lead_id` · `company_name` · `vertical` · `sub_vertical` · `city_area` · `pincode` · `contact_name` · `designation` · `email` · `phone` · `website` · `source_directory` · `email_status` (found / missing) · `segment_tier` (A/B/C) · `icp_fit_score` · `pain_hypothesis` · `buteforce_offer_match` · `proof_point` · `personalization_angle` · `outreach_status` · `sequence_step` (0–3) · `last_contacted` · `next_action` · `reply_classification` · `notes`

Sample batch already populated → `Reach out - Local/Reach_Engine_Sample_Leads_Chennai.csv` (30 leads, 25 email-ready).

---

## 3. Stage 1 — Discover / Scrape (FREE sources)

No paid APIs. Priority order by yield-per-effort, validated in the 2026-06-09 sample run:

**Import/Export + Logistics (richest email yield):**
- **Trade-association member directories** — gold. Chennai Custom Brokers Association (CCBA) accredited members PDF, CHENSAA member list PDF, FIATA India directory. Hundreds of firms with email + phone + contact name + address.
- Council/EPC member lists (FIEO, EEPC, Plastics Export Council, etc.) — public PDFs.
- Company websites — scrape `mailto:` + `/contact` pages for `info@`, `exports@`, `ops@`.
- IndiaMART seller pages (emails often gated — capture phone + site, enrich email from site).

**Clinics + Retail (phone-heavy — later/WhatsApp phase):**
- Greater Chennai Corporation hospital/clinic PDF lists, Practo/JustDial listings (phone-first), Google Maps Places (free quota) for name+phone+website, then email-scrape the website.

**Tooling (all available, all free/low-cost):**
- Tavily MCP (`tavily_search`, `tavily_extract`) for directory discovery + page extraction.
- `web_fetch` / WebSearch for specific pages.
- Claude-in-Chrome for JS-rendered directories that block plain fetch.
- Google Places API free tier for map-based discovery.

**Rule:** every lead carries `source_directory` + `source_url` for provenance and dedup.

---

## 4. Stage 2 — Enrich / Dedup · Stage 3 — Segment

- **Dedup** on normalized `company_name` + `pincode` + domain. Keep the row with the best email (role > generic > none).
- **Email verify** (free): MX-record check + syntax; soft-flag catch-all domains. No paid verifier in phase 1 — accept some bounce risk, monitored (§6).
- **Tiering:**
  - **Tier A** — Import/Export or Logistics WITH a real email → auto-pipeline.
  - **Tier B** — other vertical WITH email → auto-pipeline, lower priority.
  - **Tier C** — phone-only → **parked** until WhatsApp phase (or website email-scrape succeeds).
- **`icp_fit_score`** — High/Med/Hold from vertical + size signals (multi-office, website maturity, hiring signals per [[icp#Buying Triggers]]).

---

## 5. Stage 4 — Per-Lead Research Dossier (the core of "sharp")

For every Tier A/B lead, a Gemini agent builds a short dossier from the website + public results and writes it back to the Sheet. Five fields, exactly as Dhyan framed it:

1. **What they do** — one line: services, scale, ports/markets, specialisms.
2. **Problem they (likely) face** — the specific manual/repetitive bottleneck for that sub-vertical (e.g. freight forwarder = BoE/invoice/packing-list keying + email exception chasing).
3. **What we provide** — the matched Buteforce system (Document AI/OCR, automation agent, CV) → [[icp]] mapping.
4. **Why it's profitable for them** — quantified: hours/week reclaimed, error/escape reduction, faster turnaround → tie to a [[case_studies]] proof point.
5. **Why Buteforce** — "no consultants, no pilots, working systems; numbers over adjectives" → [[brand_bible#Manifesto]].

Output is capped (≤120 words total) so it feeds the email directly. Anything unverifiable is left blank, never invented (numbers-over-adjectives rule).

---

## 6. Stage 5–7 — Draft, Send, Follow-up

**Draft (Gemini, on-brand):**
- Templates by vertical from [[outreach_templates]], personalized with the dossier's pain + one proof point.
- Hard rules: <120 words · lead with their pain · one CTA = free 30-min AI audit · no "hope this finds you well" · no "book a free call!" desperation ([[brand_bible#Anti-Patterns Never Do This]]).

**Send (reuse `mailer.py` pattern):**
- From `outreach.buteforce.com` (NOT primary). Multipart HTML + plaintext, brand template (yellow accent).
- **Warmup ramp:** ~10/day week 1 → 20 → 30 → 50 by week 4–6. Per-domain daily cap enforced in `Config`.
- Throttle: randomized gaps, working-hours only (IST), skip weekends.

**Auto-send guardrails (since there's no per-email gate):**
- Suppression list checked before every send (unsubscribe, hard bounce, prior contact).
- One-click unsubscribe link in every email (compliance + deliverability).
- Daily **spot-check digest** to Dhyan: N queued, 5 random full drafts, bounce rate, any anomalies. Kill-switch flag in `Config` halts sending.
- Bounce monitor: if bounce rate >5% in a day, auto-pause + alert.

**Follow-up sequence (max 3, per [[marketing_engine#Campaign Rules]]):**
- Step 1 = initial. Step 2 = +5 days (the "one process you wish would handle itself" angle). Step 3 = +7 days, short breakup. Then mark `cold`.

---

## 7. Stage 8–9 — Reply Handling + Consult Booking

- **IMAP + Gemini classifier** (reuse `inbox_checker.py`): labels `interested · meeting_requested · question · not_interested · out_of_office · unsubscribe · other`.
- `interested` / `meeting_requested` → auto-reply with **Cal.com/Calendly link** + a one-line tailored hook; row moves to `Booked`; Dhyan runs the call.
- `question` → flagged to Dhyan to answer personally (not auto).
- `not_interested` / `unsubscribe` → suppression list, stop sequence.
- Free consult → if confused, free advice; then a **custom scoped solution** drafted from the dossier (this is the conversion moment, human-led).

---

## 8. Validated Finding (from 2026-06-09 sample scrape)

30 Chennai leads scraped from public directories in one pass:
- **Import/Export + Logistics: 25/25 had usable emails** (assoc. directories are rich).
- **Clinics: 5/5 were effectively phone-only** on their public pages.
- → Confirms the phase order: **B2B trade/logistics first on email-only**; clinics/retail wait for the WhatsApp phase or website email-mining. Don't waste email warmup on phone-only verticals.

---

## 9. ICP Note (supersedes the old international line for THIS engine)

The Reach Engine targets **India-local SMBs** (Chennai/TN first). This aligns with the 2026-06-08 India-first realignment of the blog engine ([[marketing_engine#Current Status]]). The authoritative [[icp]] file still shows the legacy US/UK/UAE/AU enterprise ICP — an addendum has been added there pointing here. Decision-makers for the new segments: Director/Partner/Ops Manager (imp-exp, logistics); Practice Manager/Owner (clinics); Owner/Operations (retail).

---

## 10. Phased Rollout

- **Phase 0 (now):** plan locked, sample batch scraped, schema set. ✅
- **Phase 1 (build):** Google Sheet + tabs; Python scraper for CCBA/CHENSAA/FIATA + site email-miner; dedup + verify; dossier agent; draft agent; `outreach.buteforce.com` DNS (SPF/DKIM/DMARC) + warmup; mailer + suppression + spot-check digest; IMAP classifier + Cal link auto-reply.
  - **Scaffold BUILT + VERIFIED 2026-06-09** → `Reach out - Local/reach-engine/` (config, sheets_store gspread, scraper [Tavily-powered], research, drafter, gemini, mailer, email_template, inbox_checker, followup, run.py CLI, render.yaml crons, .env.example, README). `py_compile` clean + 15/15 mocked dry-run (discovery parse, dedup, dossier, draft, branded email, SMTP send path) all PASS. Scraper uses Tavily (`TAVILY_API_KEY`).
  - **Remaining = one-time external setup only (keeps Dhyan in the loop until done):** (1) DNS: `outreach.buteforce.com` mailbox + SPF/DKIM/DMARC; (2) 6 secrets in Render env (service-account JSON w/ Editor on sheet, Gemini key, Tavily key, SMTP app-password, Cal link, warmup date); (3) deploy `render.yaml`. After that all 6 crons run daily untouched. A weekly status digest task (`reach-engine-weekly-status`) pushes a passive pulse so Dhyan doesn't have to check in.
- **Phase 2:** scale Chennai → all-Tamil-Nadu → all-India for imp-exp + logistics; add retail.
- **Phase 3:** WhatsApp channel (provider needed) to unlock phone-only clinics/retail.

---

## 11. Metrics (track in Sheet `Config`/dashboard)

Leads scraped · email-found % · sent/day · bounce % · open % (if pixel) · reply % · positive-reply % · consults booked · proposals sent · deals closed · cost (target ≈ ₹0 phase 1).

---

## 12. Open Decisions / Risks

- **Email sourcing for clinics/retail** on an email-only channel is weak → WhatsApp phase is the real unlock (needs a provider + budget decision).
- **Compliance:** India DPDP Act + global cold-email norms → keep unsubscribe + suppression rigorous; B2B role-based emails from public trade directories are lower-risk but not zero.
- **Free-verify bounce risk** — accepted in phase 1, monitored; revisit a paid verifier if bounce >5%.
- **Subdomain warmup discipline** — the single biggest deliverability lever; do not let the agent over-send early.
- **Cal tool** not yet chosen (Cal.com vs Calendly) — pick before Phase 1 reply-handling.

---

## 13. Google Drive — Source of Truth + Maintenance (LIVE 2026-06-09)

The master lead sheet now lives in Drive and is maintained from there:
- **Folder:** `Buteforce Reach Engine` — id `17x8k3Vwdfl7-RoYFjQs2CrIYhorbMRKy`
- **Master sheet:** `Reach Engine — Leads (Master)` — id `1_fMtSN7OzM5oF9nsKKuYiD6h7aiE4iM3BogRskqtvUQ` (native Google Sheet, 30 sample leads loaded, full 25-col schema)
- Owner: `dhyan.vrit@gmail.com`. **Setup step for the engine:** grant Editor to the service account `friday@buteforce.iam.gserviceaccount.com` so the Python engine can read/write this sheet (same account already used by the old review_app sheet).
- Recommended tabs to add as the engine grows: `Leads` (master), `Queue` (today's sends), `Sent`, `Replies`, `Booked`, `Suppression`, `Config` (caps, kill-switch, warmup day). For now everything is one tab.
- **Maintain-from-Drive loop:** a daily scheduled task (see §14) appends newly-scraped, deduped leads straight into this sheet — so the sheet grows itself without manual CSV handling.

## 14. Scheduling & Orchestration

Two layers — be deliberate about which runs where:

### A. Production engine crons (server-side — after Phase 1 build)
The actual send/check/follow-up must run on the engine's own host (it needs `outreach.buteforce.com` SMTP + IMAP creds), NOT in this desktop app. Recommended: **Render Cron Jobs** (the engine is already destined for Render) or free **GitHub Actions** / `cron-job.org` pinging the FastAPI endpoints. All times IST.

| Job | Cadence | What it does |
|---|---|---|
| **Discover/enrich** | Daily 06:00 | Scrape + dedup + enrich new leads → Drive sheet |
| **Research+draft** | Daily 08:00 | Build dossiers + Gemini drafts for today's `Queue` |
| **SEND** | Weekdays 09:30 | Send today's queued batch within warmup cap (10→50/day); skip weekends |
| **CHECK replies** | Every 3h, 09:00–21:00 | IMAP fetch + Gemini classify → update sheet; auto-send Cal link on `interested`/`meeting_requested` |
| **FOLLOW-UP** | Daily 10:00 | Advance due leads to step 2 (+5d) / step 3 (+7d); mark cold after 3 |
| **Health/spot-check digest** | Daily 18:00 | Email Dhyan: counts, bounce %, 5 sample drafts, anomalies; honor kill-switch |

Guardrails live in `Config`: daily cap, warmup-day counter, bounce-rate auto-pause (>5%), global kill-switch.

### B. Live now — desktop scheduled task (this app)
Until the engine ships, one recurring task already does the **discovery + Drive-maintenance** half autonomously: scrape fresh Chennai B2B leads, dedup against the master sheet, append new rows. Task id `reach-engine-daily-leads` (daily 08:00 local). Note: desktop scheduled tasks run only while the app is open; if closed at trigger time, they run on next launch. Sending/replies stay server-side for deliverability + 24/7 reliability.

## 15. MERGE with Lead Outreacher + free-stack pivot (2026-06-10)

The legacy `Projects/Lead Outreacher/` system (review_app FastAPI, `auto_enrich.py`,
`followup_engine.py`, `brevo_sequences.json`, Supabase push, "Clients detail" sheet)
and the new `reach-engine` are now **one** system. `reach-engine` is the base; the
mature ideas folded in. Single entrypoint: **`python run.py daily`** (discover→research
→send→check→followup→digest, each stage guarded).

**Cost/autonomy pivot (supersedes the Render+SMTP-subdomain plan as the default):**
- **Scheduler = GitHub Actions cron** (`.github/workflows/daily.yml`, 09:30 IST) — free, cloud, no app/server needed for a daily batch.
- **Sender = Brevo API** (`brevo_mailer.py`, `SEND_PROVIDER=brevo`) — free 300/day, built-in unsubscribe/suppression, **no DNS/SPF/DKIM warmup**. SMTP-subdomain kept as `SEND_PROVIDER=smtp` fallback (Path B in DEPLOY.md).
- **One Google Sheet** for both India-local + legacy international leads.
- Total ≈ **₹0/month** (Actions + Brevo + Gemini + Tavily + Sheets free tiers).
- Setup dropped from "DNS + mailbox + Render" to "Brevo key + push repo + paste GitHub secrets" (~15 min). See `reach-engine/MERGE.md` + DEPLOY.md Path A.
- review_app stays as an optional manual-review dashboard; old Tier-1 leads can be one-time imported into the master sheet.

## Last Updated
- 2026-06-09 — Created from greenfield spec session + first sample scrape (30 Chennai leads). Added Drive source-of-truth (live sheet), scheduling/orchestration design, and daily Drive-maintenance task.
