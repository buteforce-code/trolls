# Codex Conversations

Purpose:
- store recent session notes and unresolved threads
- preserve handoff context between Codex sessions
- avoid polluting the durable knowledge files with raw conversation noise

Do not use this file as the source of truth for stable facts if a better knowledge note exists.

## Active Threads

- **Hooter Phase 1 ✅ DONE** — Date range selector (Today/7D/30D), Bounce Rate KPI, Visit Duration Histogram
- **Hooter Phase 2 NEXT** — Zone transitions matrix (A→B), peak hours per zone, zone comparison view
- **Hooter RevOp auto-detection** is the product wedge — auto-flag missed sales vs TangoEye's manual tagging.
- **Hooter logo integrated** — Real Buteforce SVG logo (2 paths) in sidebar, login page, and favicon. Component at `src/app/components/BfLogo.tsx`.



- **Blog Agent live publishing**: `PUBLISH_DRY_RUN=true` in `dashboard/.env.local`. Flip to `false` when Dhyan is ready to start pushing posts to GitHub/TinaCMS.
- **New topic timing**: After clicking "+ New Topic", the new card appears after ~1.5s delay. Normal — Python writes to Supabase then polling picks it up.
- **Dev server restart**: After heavy bash testing sessions, restart with Ctrl+C → `npm run dev` to clear stuck TCP connections.

## Session Log

### 2026-04-19 — Blog Agent to Live Site API Integration

**Project:** `D:\Projects\Buteforce\Projects\Marketing agents\blog-agent` and `D:\Projects\Buteforce\Site\buteforce-website`

**Work done:**
1. **Agent-to-Site Gateway:** Implemented a new Next.js `/api/agent/blog` endpoint directly on the Buteforce website. This acts as a centralized receiver to parse deployed site content (`lib/data.ts` and `content/blog`) and handle authenticated Github pushes.
2. **Crash Prevention Built:** Rewrote `site_tool.py` so it executes `GET` fetch requests toward the live Buteforce API instead of crashing against hardcoded local Windows file paths when deployed on Render.
3. **Decoupled Github from Agent:** Discarded direct `github_publish` methodology from the Render agent. The agent payload is now sent directly via `POST` to the custom Buteforce gateway, enabling seamless publishing without keeping a live `GITHUB_TOKEN` vulnerable on Render.
4. **Docs Updated:** Pruned old dependencies systematically off the `.env` lists in `tech_stack.md` and `render.yaml`. Replaced with `SITE_API_URL` and secure `AGENT_SECRET_KEY` requirements.

**Next:**
- Setup environment variables on Render (`AGENT_SECRET_KEY`) and Vercel (`AGENT_SECRET_KEY`, `GITHUB_PUBLISH_TOKEN`).
- Fire test blog off the updated Swarm Publisher stack.

---

### 2026-04-16 — Hooter / RetailEye Dashboard Redesign + Production Prep

**Project:** `D:\Projects\Staff heat map` — Retail foot-traffic analytics platform (CV pipeline + Next.js dashboard)

**Work done:**

1. **Full dashboard redesign** — Replaced generic Tailwind template with a designed UI:
   - Dark sidebar (`#111216`) with subtle yellow ambient glow, nav with yellow active state
   - Glassmorphism header bar (backdrop-blur)
   - KPI metric cards with left-edge accent color bars (no icon bg boxes)
   - Section headers: uppercase tracking-widest, tiny
   - Zone engagement: ranked list with color bars
   - Live event log: **terminal style** (dark card, macOS traffic-light header, monospace lines)
   - Login page: split layout — dark brand panel left, clean form right

2. **Hardcoded localhost URLs fixed** — all pipeline URLs now read from `NEXT_PUBLIC_CV_PIPELINE_URL` env var. ZoneEditor accepts `pipelineUrl` prop. Defaults to `http://localhost:8000` for local dev.

3. **CORS hardened** — `main.py` now reads `CV_ALLOWED_ORIGINS` env var; defaults to `["*"]` only when unset (dev only).

4. **Hardcoded store_id fixed** — `main.py` now reads `STORE_ID` env var.

5. **Branding fixed** — Login page was "RetailEye", now "Hooter" throughout.

6. **ZoneEditor fixed** — Removed duplicate `Users` SVG icon (was shadowing lucide import). Fixed `ctx.fontWeight` (invalid Canvas API — moved to `ctx.font`). Error state added to save flow.

**Env vars needed for production deployment:**
- `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Supabase
- `NEXT_PUBLIC_CV_PIPELINE_URL` — public URL where cv-pipeline is hosted (e.g. GCP VM)
- `CV_ALLOWED_ORIGINS` — dashboard URL(s) for CORS
- `STORE_ID` — UUID for multi-store support
- `SUPABASE_URL` + `SUPABASE_KEY` — Python service role

**Unresolved:**
- Dashboard is Next.js → deploy to Vercel (just add env vars, connect repo)
- CV pipeline → already has `Dockerfile` + `deploy_gcp.ps1` for GCP Spot VM; set `CV_ALLOWED_ORIGINS` to Vercel URL

---

### 2026-04-18 — Graphify Vault Graph + Unified Memory for All Agents

**Work done:**

1. **Unified memory vault wired to all 4 AI tools on machine:**
   - Claude Code: `~/.claude/settings.json` → `mcpServers.obsidian-vault`
   - Cursor: `~/.cursor/mcp.json` → `mcpServers.obsidian-vault`
   - Google Antigravity: `~/.gemini/antigravity/mcp_config.json` → `mcpServers.obsidian-vault`
   - VS Code / Copilot: `AppData/Roaming/Code/User/mcp.json` → `servers.obsidian-vault`
   - GitHub Copilot instructions: `~/.github/copilot-instructions.md` — full vault protocol written
   - Global CLAUDE.md updated with "Unified Memory Vault" rules section
   - `VAULT_README.md` written as master orientation doc for all agents

2. **Graphify knowledge graph built on vault:**
   - 137 nodes · 150 edges · 36 communities (Leiden clustering)
   - God nodes: Cold Outreach Templates (11 edges), ICP (10), Master Index (9), Lead Gen (9), Hooter Plan (8)
   - 6 hyperedges: Brand Identity System, CV Analytics Stack, Proof-Content-Sales Loop, Per-Vertical Sales System, Swarm Pipeline, Vault Memory Protocol
   - Outputs: `graphify-out/graph.json`, `graphify-out/graph.html`, `graphify-out/GRAPH_REPORT.md`
   - Obsidian vault: `graphify-out/obsidian/` — 173 linked notes

3. **Hooter YouTube pipeline tested:**
   - yt-dlp resolved `watch?v=MNn9qKG2UFI` to direct Google CDN URL
   - OpenCV opened stream successfully; pipeline ran at 8.8 FPS with 3 active DeepSORT tracks

**Next — Phase 2 Hooter:**
- Zone transitions matrix (A→B heatmap from `zone_transitions` view)
- Peak hour per zone
- Zone comparison side-by-side

---

### 2026-04-17 — Hooter Logo Integration + Phase 1

**Work done:**

1. **Real Buteforce logo integrated** everywhere:
   - `public/favicon.svg` — logo paths on dark `#111216` rounded square, paths filled yellow `#facc15`
   - `src/app/components/BfLogo.tsx` — shared server+client compatible SVG component
   - Sidebar brand area — replaced "H" placeholder with `<BfLogo size={32} color="#facc15" />`
   - Login page — both desktop brand panel and mobile header use real logo

2. **Phase 1 — Date range selector**
   - Header now has Today / 7D / 30D pill-segment control with animated active-tab styling
   - `fetchAnalytics` queries filtered by `.gte('timestamp', from)` based on selected range
   - All KPI captions and chart titles adapt to the selected range label

3. **Phase 1 — Bounce Rate KPI**
   - New 5th KPI card: "Bounce Rate" (% of dwell events < 30s)
   - KPI grid expanded from 4 to 5 columns (`xl:grid-cols-5`)
   - Accent color: orange `#f97316`

4. **Phase 1 — Visit Duration Histogram**
   - `buildDwellBuckets()` helper groups dwell seconds into 6 buckets: `<15s / 15–30s / 30–60s / 1–3m / 3–10m / >10m`
   - Bar chart below Traffic Profile using rainbow cells (blue → yellow → green encoding short → engaged → high-intent)
   - Bounce marker caption under histogram shows bounce % and threshold explanation

5. **Bug fixes**
   - `src/utils/supabase/server.ts` — updated to `async function createClient()` + `await cookies()` for Next.js 15 compatibility
   - Recharts `Tooltip formatter` types fixed (no more `v: number` hard-cast)
   - Login `signIn` action updated to `await createClient()`
   - Zero TS errors, clean `next build`

**Next — Phase 2:**
- Zone transitions matrix (zone A → zone B heatmap using `zone_transitions` view)
- Peak hour per zone (hour with max visits per zone_id)
- Zone comparison view side-by-side

---

### 2026-04-15 — Blog Agent Full Build + UI Fixes

**Work done across 3 context windows:**

1. **Codebase audit** — Mapped full pipeline: ADK orchestrator, 4-stage agent swarm, Supabase DB, Next.js dashboard, TinaCMS publishing.

2. **Site integration** — Connected research agents to `D:/Projects/Buteforce/Site/buteforce-website`. Research agent now reads existing blog posts (avoid duplicates) and `lib/data.ts` (brand alignment). 9 research sources total.

3. **TinaCMS alignment** — Fixed writer agent frontmatter to match TinaCMS schema exactly (`title, description, date, tags, image`). Fixed filename format to `{slug}.mdx`. Updated `GITHUB_REPO=buteforce-code/ButeForce-Site`.

4. **Dashboard redesign** — Full light theme rewrite per brand bible (#fff bg, #0a0a0a text, #e8ff00 accent). Real B-mark SVG in nav. Active pipeline step uses accent yellow.

5. **Delete + recovery flows** — Added `--delete` and `--reset` CLI args to `run.py`. New API routes `delete` + `reset`. Dashboard shows × delete on every card (two-step confirm). Failed topics show "Reset to Review" or "Re-run Research" with context-aware message (no more "check logs" blocking state).

6. **Bug fixes (2026-04-15)**:
   - Fixed `onMouseEnter/onMouseLeave` DOM mutation → CSS `.card-delete-btn` hover class
   - Fixed `handleReset` setState-after-unmount → `useRef` mounted guard
   - Added 1.5s delay before `onCreated()` so Python has time to write topic to DB
   - Corrected `GITHUB_REPO` in `dashboard/.env.local`

**Key architecture decision (standing)**:
Never use `SUPABASE_SERVICE_KEY` in Next.js route handlers on Windows. All writes go through `spawn('python', ['run.py', ...])` detached. Only anon key reads in Next.js.

---

### 2026-04-12

- Connected the workspace to the Obsidian vault through a local `.agents` junction.
- Added Codex bootstrap and active-brain skills so future sessions can retrieve focused context from the vault.
- Added a search helper script at `.codex/skills/obsidian-active-brain/scripts/obsidian_memory.py`.
- Standardized vault retrieval rules in `workflows/codex-active-brain.md`, `workflows/load-memory.md`, and `rules/memory.md`.
