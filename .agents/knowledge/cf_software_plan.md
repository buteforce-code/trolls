# CF Software — Product & Technical Plan

> AI-powered call overlay that surfaces answers from the user's Obsidian vault in real-time during live calls (Zoom, Meet, Teams). Invisible to screen share.

## ⚠️🔴 LEGAL / IP STATUS — READ BEFORE ANY EXTERNAL ACTION
### This section is updated by AI analysis. Last reviewed: 2026-06-03.

---

> **BOTTOM LINE: This idea is completely exposed. There is no legal barrier stopping any funded competitor from copying it today. The only protection is how fast you ship and how little you reveal about the mechanism.**

---

**CF Software has ZERO legal binding to Dhyan or Buteforce.** As of 2026-06-03:

| Protection | Status | Risk Level |
|---|---|---|
| Patent (method/system) | ❌ None filed | 🔴 CRITICAL — architecture can be copied freely |
| Trademark (name) | ❌ None — name not even chosen | 🔴 CRITICAL — anyone can register "Elute", "Vale", "Kache" etc. tomorrow |
| Copyright (code) | ⚠️ Implicit (code is copyrighted by author on creation) | 🟡 Medium — protects literal code only, not the idea |
| Design rights | ❌ None | 🟡 Medium — UI can be copied |
| Publication / Priority date | ❌ Nothing dated/notarised publicly | 🔴 CRITICAL — no proof you invented it first |
| Company incorporation | ❌ None — product has no legal home | 🔴 CRITICAL — no entity to assign IP to |
| IP assignment agreement | ❌ None | 🔴 CRITICAL — product not legally assigned to anyone |
| NDAs (anyone shown internals) | ❌ None in place | 🔴 CRITICAL — anyone seen the build can replicate freely |
| Trade secret protection | ⚠️ Possible IF architecture stays confidential | 🟡 Medium — only if you don't publish it |

### What This Means in Plain Language

If the concept — "real-time overlay that uses YOUR personal Obsidian vault as a Graph RAG knowledge base to answer questions during live calls" — becomes public knowledge before you have either:
1. Significant traction (users, reviews, social proof), OR
2. Basic legal protection (trademark + some form of dated proof),

then a funded competitor can copy the **entire product including the core insight** with zero legal recourse available to you. Cluely ($120M valuation) could ship this in 3-4 weeks. Littlebird (already has memory + overlay) could add a "vault" integration in 2 weeks. Any YC batch could do it.

### What They CAN'T Easily Copy (Your Real Moat)
- Your personal knowledge of the exact LightRAG dual-level architecture (entity + community) optimised for Obsidian wikilinks — this is deep and took research time
- Your Windows-first positioning + WASAPI loopback approach
- Your specific latency budget and the stack decisions that achieve it
- Your vault-parser for Obsidian's proprietary wikilink format

**These are only a moat as long as they stay private.** The moment they're published, they become commoditised.

### Concrete Actions — Priority Order (Not Legal Advice — Verify with a Professional)

**Do in the next 2 weeks (zero-cost):**
1. **Create a dated, private proof of authorship** → Email the `cf_software_plan.md` + current architecture diagram to yourself at a Gmail/Outlook address. The email timestamp creates evidence. Also: push to a private GitHub repo with commit history — git commits are timestamped and signed.
2. **Lock the product name** from the naming candidates (Elute / Vale / Kache / Mnemo / Cortex). Once locked, do a free trademark search at IP India (ipindia.gov.in) and USPTO (tmsearch.uspto.gov).
3. **Write the NDA conversation** — anyone who has seen or will see the architecture should get an informal conversation: "This is confidential, I'm treating it as proprietary." Document the conversation in this file.

**Do before any public demo or marketing:**
4. **File a trademark application** on the product name (once chosen). India: ~₹4,500/class via IP India. US: ~$250/class via USPTO. This is the single highest-value legal step for the budget.
5. **Incorporate Buteforce** (or use existing entity) and assign the CF Software IP to that entity via a written IP assignment agreement. Even a self-drafted document is better than nothing.
6. **Add a copyright notice** to all source files: `// Copyright (c) 2026 Dhyan Karthikeyan / Buteforce. All rights reserved.`

**Do before public launch:**
7. **Draft a basic Terms of Service + Privacy Policy** for the app — these establish the company's relationship to the software formally.
8. **Consult a tech IP lawyer** — one session, not a retainer. Ask specifically about: software copyright in India, trade secret documentation, and whether a provisional patent makes sense.

### Operating Rules Until Legal Status Changes
1. **Soft-market the OUTCOME, not the mechanism.** Say: "your second brain, live on every call." Do NOT say: "Obsidian Graph RAG with entity + community dual-level retrieval." The outcome is the hook. The mechanism is the moat.
2. **No public demos that show the vault-as-knowledge-base architecture** until basic trademark protection exists.
3. **Anyone shown the codebase = write their name in this file + have the NDA conversation.**
4. **Never mention LightRAG, the dual-level retrieval, or the Obsidian wikilink parser** in public content. These are the technical specifics that separate CF Software from anything a competitor could build in a sprint.
5. **Update this block immediately** if any of the above legal items change status.

> **Who has seen the internals:** Dhyan (founder), Claude AI agents (this session). No external humans as of 2026-06-03.

## Status
- **Phase**: Phase 0 — Project scaffolding done, dev environment set up
- **Current Sprint**: Product evolution / architecture refinement (LightRAG migration)
- **Last session**: 2026-06-01

## Product Summary
- **Type**: Native desktop app (Tauri 2.x + React + Python sidecar)
- **Moat**: Only overlay tool that uses YOUR personal Obsidian vault as knowledge base (Graph RAG), not generic AI
- **Competitors**: Cluely ($20M+ raised, ~$120M val, DATA BREACH 2025), Parakeet (credit-based), Pluely (OSS Tauri), Medhly (<50ms), Trellus (YC, sales coaching)
- **Pricing target**: $9.99/month Pro tier, API cost ~$10-20/month per heavy user
- **Key insight**: 15+ competitors, ZERO in the personal-knowledge + real-time overlay quadrant

## Three Product Modes
1. **Sales Wingman** (Primary — Buteforce dogfood): Real-time answers from vault during client calls
2. **Interview Coach**: Personal career facts surfaced during job interviews
3. **Team Meeting Intelligence**: Project status and context during internal meetings

## Architecture (Updated June 2026)
```
Tauri 2.x (Rust) ↔ WebSocket (:8765) ↔ Python FastAPI sidecar
                                        ├─ AudioCapture (WASAPI / BlackHole)
                                        ├─ DeepgramStreamer (Flux WebSocket STT, /v2/listen)
                                        ├─ VaultParser (Obsidian .md + wikilinks)
                                        ├─ LightRAG Engine (dual-level: entity + community)
                                        │   ├─ Low-level: entity search (specific facts)
                                        │   └─ High-level: community traversal (multi-hop)
                                        ├─ Cross-encoder reranking (BAAI/bge-reranker)
                                        └─ Groq LLaMA 3.1 8B (streaming answer)
```

### ⚡ Key Architecture Change (June 2026)
- **LightRAG** replaces LlamaIndex PropertyGraphIndex (6000× cheaper, incremental indexing)
- **Kuzu is redundant** — LightRAG manages its own graph store
- **LanceDB retained** as raw vector backup only
- **Neural Composer** plugin validates this approach in production Obsidian vaults

## Tech Stack (Locked — Updated June 2026)
| Component | Tool | Latency |
|---|---|---|
| Desktop | Tauri 2.x | — |
| Frontend | React 18 + TypeScript + Vite + Framer Motion | — |
| STT | Deepgram Flux (WebSocket, /v2/listen) | <300ms streaming |
| Overlay LLM | Groq LLaMA 3.1 8B Instant | 50-70ms TTFT |
| Offline LLM | Claude 3.5 Haiku | N/A |
| Embeddings | nomic-embed-text or all-MiniLM-L6-v2 (local) | 50-80ms |
| RAG Engine | **LightRAG** (dual-level: entity + community) | <20ms |
| Vector DB | LanceDB (embedded, backup) | <5ms |
| Reranking | BAAI/bge-reranker (cross-encoder) | ~10ms |
| Audio (Win) | WASAPI loopback | 0ms |
| Audio (Mac) | BlackHole 2ch + CoreAudio | 0ms |
| IPC | WebSocket (port 8765) | — |
| Overlay UX | Click-through via setIgnoreCursorEvents | — |

## Latency Budget (Hard ceiling: 800ms)
- Deepgram Flux streaming: ~100-300ms
- Question classifier: ~5ms
- LightRAG retrieval (entity + community): ~20ms
- Cross-encoder reranking: ~10ms
- Groq LLaMA (150 tokens): ~230ms
- React render: ~5ms
- **Total target: ~370-570ms**

## Project Directory
```
d:\Projects\Buteforce\Projects\client facing call ai\Client Facing\cf-software\
├── src/                  ← React frontend (Overlay.tsx, App.tsx, useWebSocket.ts)
├── src-tauri/            ← Rust (lib.rs: screen-capture exclusion, sidecar spawn)
├── sidecar/              ← Python backend (main.py, audio.py, transcriber.py, rag_engine.py, vault_parser.py)
├── .github/workflows/    ← release.yml CI/CD
├── CLAUDE.md             ← Full project conventions for AI agents
└── package.json          ← React + Tauri deps
```

## Phase Plan (Updated June 2026)
- **Phase 0 (complete)**: Dev environment setup, validate build chain
- **Phase 1 (Weeks 1-2)**: Windows MVP — audio→STT→LightRAG→overlay
- **Phase 2 (Weeks 3-4)**: Graph intelligence, multi-hop queries, prefetch pipeline
- **Phase 3 (Weeks 5-6)**: Full knowledge layer — database connectors, post-call vault updates
- **Phase 4 (Week 7+)**: Code signing, CI/CD, onboarding flow, premium UI, beta launch

## Key Constraints
- Screen-capture exclusion is NON-NEGOTIABLE (WDA_EXCLUDEFROMCAPTURE on Win, NSWindowSharingNone on Mac)
- Overlay must NEVER steal focus from the call window (setIgnoreCursorEvents for click-through)
- API keys stored in OS keychain only (tauri-plugin-stronghold)
- Claude CANNOT be used for overlay LLM (597ms TTFT — too slow)
- Local-first architecture — vault data never leaves the machine (competitive advantage vs Cluely data breach)

## Naming Candidates
Top 5: **Elute** (chemistry elution + compute), **Vale** (valence + Latin strength), **Kache** (cache + French hidden), **Mnemo** (Greek memory), **Cortex** (brain recall)

## Competitive Intelligence (June 2026)
- Cluely: $20M+ raised, ~$120M val, pivoted to professional assistant, DATA BREACH in 2025
- Parakeet: Credit-based ($29-88/use), GPT-5/Claude 4.0 Sonnet, detectable by proctoring
- New entrants: Medhly (<50ms, SOC 2), LockedIn AI, InterviewMan, Final Round AI
- Sales coaching: Trellus (YC, $100-150/mo), Balto, Salesken, Abstrakt, Cogito
- Meeting assistants: Fathom (free tier), tl;dv (EU), Read AI, Avoma
- **GAP**: Zero competitors in personal-knowledge + real-time overlay quadrant

## Related Research Documents
- [[CF Software - Product Vision]]
- [[CF Software - Deep Tech Research]]
- [[CF Software - Competitor Analysis & Final Stack]]
- [[CF Software - Technical Implementation Deep Dive]]
- [[CF Software - UI Design Direction]]
- [[CF Software - Naming Brainstorm]]

---

## 🧠 DEEP ANALYSIS — State of CF Software (June 3, 2026)

*Written by AI analysis of vault, competitor teardowns, and architecture docs. Update after each major session.*

### What's Real and What's at Risk

**The signal:** The personal-knowledge + real-time overlay quadrant is genuinely empty. After a full competitive scan (Cluely, Littlebird, Parakeet, Medhly, Trellus, Balto, Salesken, Fathom, tl;dv, Read AI, Avoma, InterviewMan, Final Round AI, LockedIn AI), not one of them does what CF Software does: uses YOUR vault, YOUR knowledge, YOUR context — not generic internet AI. This is a real product gap, not a perceived one.

**The moat assessment:**

| Moat | Strength | Durability | Verdict |
|---|---|---|---|
| Personal vault as knowledge base | 🔥 Very high | Medium — copyable once public | Core insight. Protect until traction. |
| LightRAG dual-level entity + community retrieval | 🔥 Very high | High — deep technical edge | Never describe publicly |
| Local-first / no cloud | ✅ Strong | High — structural | Safe to market |
| Sub-500ms total latency | ✅ Strong | Medium — achievable by others | Marketable as fact, not mechanism |
| 30-40MB install (vs 1.5GB Littlebird) | ✅ Strong | High — Tauri architecture | Marketable. Use specific numbers. |
| Windows-first | ✅ Strong | High — competitors are Mac-first | Marketable. Underserved market. |
| Post-call vault enrichment (Phase 3) | 🔥 Very high | High — deeply unique | Don't mention publicly until built |

**What's fragile:**

1. **Phase 1 is not done.** Until audio→STT→LightRAG→overlay works end-to-end on a live call, the product doesn't exist. Marketing before Phase 1 ships creates expectations you can't meet.
2. **The Python sidecar will be ~358MB with Torch.** This is real install weight — not the 30-40MB of the Tauri shell. Users will see the full size. Manage expectations in onboarding.
3. **Deepgram cost at scale.** Deepgram Flux is excellent but not free. Need to model the cost per active user per month before pricing.
4. **The name isn't chosen.** Without a name, you can't trademark, can't build a brand, can't do a waitlist. **Choosing the name is blocking everything downstream.**
5. **No onboarding flow.** The vault setup path (vault path selection, initial graph indexing, first query) is unbuilt. This is the hardest UX problem in the product.

**What's strong:**
1. The architecture decisions (LightRAG migration) are correct. 6000× cheaper than LlamaIndex PropertyGraphIndex + incremental indexing = production-viable.
2. The Littlebird teardown gave you a concrete list of patterns to adopt (command palette, Tiptap, Shiki, tray states, premium typography) and a list to avoid (cloud-auth, Electron, passive ambient). This is rare clarity.
3. The three product modes (Sales Wingman, Interview Coach, Team Meeting) are well-scoped and sequenced. Sales Wingman is the right beachhead — it's Buteforce's own dogfood use case.

### Competitive Threat Matrix (Who Could Copy This and When)

| Competitor | Capability to Copy | Speed | Trigger | Threat Level |
|---|---|---|---|---|
| Cluely ($120M val) | Very high — full team, funded | 2-4 weeks | Sees a demo or LinkedIn post describing the vault angle | 🔴 CRITICAL |
| Littlebird | High — already has memory + overlay + Tauri architecture known | 2-3 weeks | Sees a demo showing Obsidian integration | 🔴 CRITICAL |
| YC batch startup | High — technical founders | 4-6 weeks | Sees product or pitch | 🟡 High |
| Parakeet | Medium — credit-based, different arch | 6-8 weeks | Sees traction | 🟡 Medium |
| Open-source project | Medium — community pace | 8-16 weeks | Gets posted on HN/Reddit | 🟡 Medium |

**Trigger to watch:** Do NOT post on Hacker News, Product Hunt, or Reddit until Phase 1 is live AND either a waitlist exists OR basic trademark is filed.

---

## 📣 SOFT MARKETING PLAYBOOK — Phase 0 → Phase 1

*The goal: build an audience for the problem before revealing the solution.*

### The Principle
Market in layers. Each layer reveals slightly more, but the critical insight (vault-as-knowledge-base + Graph RAG) stays private until there is traction or protection. The sequence is: **Problem → Pain → Category → Teaser → Product**.

### Layer 1: Problem Marketing (Safe to start NOW)
Post about the PROBLEM. No mention of CF Software at all. Build awareness that the problem exists and is worth solving.

**Post ideas (LinkedIn/X — can go live this week):**

> "You're on a client call. They ask a question you KNOW the answer to — it's somewhere in your notes. You fumble. You say 'let me get back to you.' You lose credibility in 3 seconds. This happens to everyone and almost nobody talks about it."

> "The average professional has 3,000+ notes, docs, and emails that could help them on any given call. Access time: 4-6 minutes minimum. Usefulness during a live call: zero."

> "Preparation covers 80% of calls. The other 20% is the questions you didn't see coming. That 20% is where deals are lost, candidates get rejected, and managers lose trust."

> "The irony of second brains: you spend hours building a perfect note system that's completely useless when you need it most — during a live conversation."

**Why this is safe:** These posts establish YOU as someone thinking deeply about this problem space. They build audience. They don't reveal anything about what you're building. They create demand for a solution that doesn't yet exist publicly.

### Layer 2: Category Creation (Start after Phase 1 is 50% done)
Begin defining a new category without naming the product. Prime the market to want what you're building.

**Post ideas:**

> "What would an AI assistant look like if it knew YOUR specific context — your clients, your projects, your terminology — instead of generic internet training data? Not someday. Right now, on a live call."

> "There are AI tools that listen to your calls. There are AI tools that know information. What doesn't exist yet: one that knows YOUR information, live, in real time. That gap is where the next 10x productivity tool lives."

> "The best call assistant would be completely invisible. You'd never need to look at it — it just surfaces the right answer exactly when you need it, faster than you can search your own notes."

**Why this is safe:** Still no product name, no mechanism described, no Obsidian angle. But you're building an audience that will immediately recognise CF Software when it launches.

### Layer 3: Build in Public (Start after Phase 1 ships)
Begin teasing the build WITHOUT revealing the vault/Graph RAG mechanism. Show the hard engineering, not the insight.

**Safe to share publicly:**
- "Building a desktop app that has to process audio in real-time and return an answer in under 500ms. Here's the latency breakdown."
- "The hardest problem in building a real-time call assistant isn't the AI. It's making the overlay invisible to screen share. Here's how that works."
- "Our app installs in 30MB. Comparable tools are 1.5GB. Here's the engineering decision that made the difference." (Tauri vs Electron — safe, this is public knowledge)
- Demo clips of the overlay appearing (WITHOUT showing the vault connection)

**NOT safe to share publicly yet:**
- "Powered by your Obsidian vault"
- "Graph RAG on your personal knowledge base"
- "Entity + community dual-level retrieval"
- The `rag_engine.py` architecture or any code

### Layer 4: Waitlist (Launch when Phase 1 is live + name is chosen + trademark filed)

**Landing page copy (outcome-only, mechanism-hidden):**
```
Headline: Your second brain. Live on every call.
Sub: The AI assistant that knows YOUR context — not the internet's.
CTA: Join the waitlist → [email]
```

**What to show:** the overlay UI appearing on screen during a call. Clean, minimal, fast.
**What NOT to show:** vault connection, Obsidian logo, any mention of how it retrieves answers.

### Layer 5: Product Launch (Phase 4 — beta)
Full reveal. By this point you need at least one of:
- Trademark filed on the name
- Significant traction (500+ waitlist signups)
- Incorporation completed

**Launch channels in order:**
1. Personal LinkedIn (Dhyan @dhyankarthik) — founder story + product reveal
2. X/Twitter thread — build-in-public narrative conclusion
3. Hacker News "Show HN" — engineer credibility
4. Product Hunt — discoverability
5. Relevant subreddits (r/ObsidianMD, r/salesforce, r/recruiting) — targeted

### What to NOT Do Before Phase 1 Ships
- ❌ No Product Hunt pre-launch or coming soon
- ❌ No HN post
- ❌ No detailed blog post explaining the architecture
- ❌ No demo video showing the vault integration
- ❌ No cold outreach to journalists or influencers
- ❌ No posting in Obsidian community forums (too specific — reveals the angle)

### The ONE Marketing Thing to Do This Week
Pick the product name. Everything else is blocked on it. Run it through the trademark search. Once the name is locked, you can:
- File the trademark
- Build the landing page
- Start Layer 1 problem posts
- Create the waitlist

---

## 🔒 PEOPLE WHO HAVE SEEN THE INTERNALS

| Person | Date | What They Saw | NDA Status |
|---|---|---|---|
| Dhyan Karthikeyan (founder) | All sessions | Full architecture, vault plan, code | N/A — founder |
| Claude AI (Cowork session) | 2026-06-03 | Full vault, architecture, competitor analysis | N/A — AI assistant |

> **Rule: Every human who sees the internals gets a name in this table and an informal NDA conversation.**

---

*Updated: 2026-06-03 — Full deep analysis added, legal/IP section expanded with action table and threat matrix, soft marketing playbook added (5 layers). Last reviewed by: AI analysis + Dhyan.*
