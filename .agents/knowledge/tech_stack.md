---
links: "[[INDEX]] | [[dhyan_psychology]] | [[founder]] | [[brand_bible]] | [[marketing_engine]]"
type: technical
last-updated: 2026-04-28
---

# Tech Stack — Buteforce Systems

> All conventions here align with [[dhyan_psychology#Decision Making Principles]] — always custom, never generic.
> Brand design tokens that inform the code → [[brand_bible#Website Design Language]].

## Website (buteforce.com)

| Layer | Technology | Notes |
|---|---|---|
| Framework | Next.js 15 (App Router) | React 19, latest stable |
| Styling | TailwindCSS v3 | Custom design tokens, light-first brand rule; dark mode is being removed |
| CMS | TinaCMS | Headless, Git-backed content |
| Animations | Framer Motion v11 | All micro-animations |
| Icons | Lucide React | Consistent icon set |
| Email | Resend API | Transactional email from contact form |
| Hosting | Vercel | Auto-deploy on push |
| Package Manager | npm | Standard |
| Language | TypeScript 5 | Strict mode |

### Key File Paths
- `lib/data.ts` — Single source of truth for all site content and config
- `app/page.tsx` — Homepage composition
- `components/hero.tsx` — Hero section with video background + proof strip
- `components/animations.tsx` — Reusable Framer Motion wrappers (BlurText, FadeContent, StaggerContainer, etc.)
- `components/footer.tsx` — Footer with contact/location → [[founder#Identity]]
- `components/about-founder-section.tsx` — Founder identity section → [[founder]]
- `components/logo-proof-section.tsx` — Client logo band → [[brand_bible#Homepage Required Sections]]
- `public/images/founder.jpg` — Dhyan's passport photo

### Environment
- Dev server: `npm run dev` (TinaCMS + Next.js)
- No `.env` values currently required for basic dev

---

## AI Pipeline Stack

| Tool | Use Case |
|---|---|
| Python 3.x | All scripting and AI pipeline code |
| Supabase | Primary database (Postgres + Auth + Storage) → [[marketing_engine#Outreach Pipeline Architecture]] |
| YOLOv8 | Object detection in computer vision projects |
| PaddleOCR | Document text extraction |
| Claude API | Legacy or older-tool LLM integration only |
| Mistral | Lightweight LLM for classification |
| OpenAI API | Embeddings and GPT tasks |
| Google Gemini | Preferred reasoning engine for autonomous agents and lightweight server-side tools via Google AI Studio / Gen AI SDK |
| Telegram Bot API | Real-time operation notifications |
| n8n | Workflow automation (some pipelines) |

---

## Lead Outreacher Review App (d:\Projects\Buteforce\Projects\Lead Outreacher\review_app)

> Manual review-and-send tool for high-value Tier 1 outreach.
> **LIVE on Render:** `https://buteforce-outreach.onrender.com`
> Last updated: 2026-04-28

| Layer | Technology | Notes |
|---|---|---|
| Backend | FastAPI + uvicorn | Deployed on Render free tier (`srv-d7ng7h3eo5us73f9p6rg`) |
| UI | Server-rendered HTML | Inter font, Buteforce brand tokens, notification center |
| Queue / Data | Google Sheets | `sheets_store.py` — SHEET_ID `1KghW03YIgrvWhSPzKTgw_uyGU2BcMVtB5nP1tPZUdfQ`, tab "Clients detail" |
| Auth to Sheets | Service account JSON | `friday@buteforce.iam.gserviceaccount.com` — must be an Editor on the sheet |
| Draft Generation | Gemini Developer API | `generator.py` — `gemini-2.5-pro`, structured JSON output |
| Email Delivery | SMTP multipart | `mailer.py` sends branded HTML + plain-text fallback via `admin@buteforce.com` |
| Email Template | Custom HTML | `email_template.py` — yellow accent bar, brand header, signature, footer tagline |
| Reply Notifications | IMAP4_SSL + Gemini | `inbox_checker.py` polls `imap.gmail.com:993`, Gemini classifies replies |
| Notification State | File (`notif.json`) | `notif_store.py` — ephemeral (resets on redeploy, re-fetched from IMAP on load) |

### Key File Paths
- `review_app/app.py` — FastAPI routes (queue, generate, send, skip, reset, notifications)
- `review_app/generator.py` — Gemini email draft generation
- `review_app/mailer.py` — multipart SMTP send
- `review_app/email_template.py` — branded HTML email builder
- `review_app/sheets_store.py` — Google Sheets read/write (replaces `queue_store.py` when env var set)
- `review_app/queue_store.py` — fallback file-based store (used locally without Sheets)
- `review_app/inbox_checker.py` — IMAP reply fetcher + Gemini classifier
- `review_app/notif_store.py` — notification persistence + poll throttle
- `review_app/templates/index.html` — full SPA review UI with notification center
- `render.yaml` — Render deploy config

### Notification Classification Labels
`interested` · `meeting_requested` · `question` · `not_interested` · `out_of_office` · `unsubscribe` · `other`

Each reply gets: `classification`, `reason` (one sentence), `suggested_action` (specific next step)

### Render Environment Variables
| Var | Value |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio key |
| `GEMINI_MODEL` | `gemini-2.5-pro` |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `admin@buteforce.com` |
| `SMTP_PASS` | Google Workspace App Password |
| `IMAP_HOST` | `imap.gmail.com` |
| `IMAP_PORT` | `993` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full service account JSON (single-line) |
| `SHEET_ID` | `1KghW03YIgrvWhSPzKTgw_uyGU2BcMVtB5nP1tPZUdfQ` |
| `SHEET_NAME` | `Clients detail` |

### Known Issues / Watchlist
- Free Render tier spins down on inactivity — 50s+ cold start on first request
- `notif.json` is ephemeral; read state resets on redeploy (replies re-fetched from IMAP automatically)
- IMAP requires "IMAP access" enabled in Google Workspace Admin for `admin@buteforce.com`
- Tier 1 threshold: `spend_usd >= 200,000` (column K of sheet, parsed from `$230K` etc.)

---

## Hooter Project (d:\Projects\Staff heat map)

> **Previously called "RetailEye" in some files — now unified as "Hooter".**
> **Status:** Product-first phase. SaaS/Stripe billing intentionally deferred until demo-ready.
> **Last updated:** 2026-04-16

| Layer | Technology | Notes |
|---|---|---|
| CV Pipeline | Python · YOLOv8n · DeepSORT | `cv-pipeline/main.py`, 5 FPS on CPU |
| Streaming | FastAPI + uvicorn | MJPEG at `{CV_PIPELINE_URL}/stream` |
| Zone Tracking | `cv2.pointPolygonTest` | Polygon geofences via `--zones` JSON or POST `/api/zones` |
| DB / Auth | Supabase (Postgres + Storage + Realtime) | `store_events` table with RLS; `store_zones` bucket for heatmaps |
| Dashboard | Next.js 16 · React 19 · TailwindCSS v4 | `dashboard-ui/src/app/page.tsx` |
| Charts | Recharts 3 | AreaChart + BarChart with Cell |
| Animations | Framer Motion 12 | All KPI cards and zone bars |

### Key File Paths
- `schema.sql` — Supabase schema: `stores`, `store_events`, `zone_analytics` view, `hourly_traffic` view
- `cv-pipeline/main.py` — CV daemon: YOLO detection → DeepSORT → zone dwell → Supabase emit
- `dashboard-ui/src/app/page.tsx` — Full analytics dashboard (redesigned 2026-04-16)
- `dashboard-ui/src/app/components/ZoneEditor.tsx` — Canvas-based zone polygon editor
- `dashboard-ui/src/app/login/page.tsx` — Split-panel login page
- `.env.example` — All required env vars documented
- `deploy_gcp.ps1` — GCP Spot VM deployment script
- `zlog.txt` — Architecture & decision log

### Production Env Vars (required for online hosting)
| Var | Where | Purpose |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Next.js | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Next.js | Supabase anon key |
| `NEXT_PUBLIC_CV_PIPELINE_URL` | Next.js | Public URL of FastAPI backend |
| `CV_ALLOWED_ORIGINS` | Python | CORS: comma-sep allowed origins |
| `SUPABASE_URL` | Python | Supabase URL (service role) |
| `SUPABASE_KEY` | Python | Supabase service role key |
| `STORE_ID` | Python | UUID for this store (multi-tenant) |

### Deployment
- **Dashboard → Vercel**: Connect `dashboard-ui/` subdirectory, add env vars above
- **CV Pipeline → GCP**: Run `deploy_gcp.ps1`, set `CV_ALLOWED_ORIGINS` to Vercel URL

### Test Video Sources
- **Oxford Town Centre**: Kaggle / Academic Torrents — preferred
- **ffmpeg RTSP loopback**: `ffmpeg -re -i demo.mp4 -f rtsp rtsp://localhost:8554/stream`
- **YouTube VOD**: `yt-dlp -f best "<url>" -o demo.mp4`

### Known Issues
- Heatmap 404 in demo mode — cv-pipeline writes to `cv-pipeline/` dir, not Next.js `public/`. Copy or symlink to fix locally.
- `zone_analytics` VIEW must be applied to Supabase manually via SQL editor.

---

## Development Conventions
- All site content lives in `lib/data.ts` — never hardcode content in components
- Components must be kept focused and reusable — no god components
- Use semantic HTML throughout (accessibility + SEO)
- All new sections follow the `FadeContent` / `StaggerContainer` animation pattern
- Phone and address always pulled from `COMPANY` object in `data.ts` → [[founder#Identity]]

---

---

## Blog Agent Pipeline (d:\Projects\Buteforce\Projects\Marketing agents\blog-agent)

> Autonomous blog content pipeline: research → human review → write → human review → publish to TinaCMS.

### Architecture

| Layer | Technology | Notes |
|---|---|---|
| AI Orchestrator | Google ADK (LlmAgent + Runner + InMemorySessionService) | Python, 3-retry wrapper |
| LLM | Gemini 2.5 Flash | Via Google AI Studio — NOT Vertex AI (billing issues) |
| Database | Supabase (Postgres) | `topics` + `blog_posts` tables |
| Research Tools | Tavily, YouTube API, Reddit, HN, site_tool | 9 sources total |
| Dashboard | Next.js 15 App Router (port 3005) | Light theme, brand B-mark |
| CMS Target | TinaCMS on buteforce-code/ButeForce-Site | Git-backed, content/blog/*.mdx |

### Pipeline Stages

```
queued → researching → verifying_research → writing → verifying_draft → publishing → published
                               ↑ human review             ↑ human review
```

### Key File Paths

- `run.py` — CLI: `--topic`, `--approve`, `--reject`, `--delete`, `--reset`, `--status`, `--list`
- `swarm/orchestrator.py` — Stage runner, 3-retry wrapper, DB upsert via Supabase
- `swarm/agents/research.py` — 9-tool research agent with site awareness (avoids duplicate posts)
- `swarm/agents/writer.py` — Draft + humaniser agent; outputs TinaCMS-exact frontmatter
- `swarm/tools/github_tool.py` — Publishes .mdx to Buteforce Site via Custom Agent Webhook (`/api/agent/blog`)
- `swarm/tools/site_tool.py` — Reads existing posts + lib/data.ts remotely via `GET /api/agent/blog` to stay aware of brand/duplicate data when published on Render.
- `dashboard/app/page.tsx` — Topic grid with status badges, delete, filter
- `dashboard/app/topic/[slug]/page.tsx` — Detail: pipeline steps, research digest, draft preview, approve/reject
- `dashboard/app/api/` — Route handlers: topics, topic/[slug], run, approve, reject, delete, reset
- `dashboard/lib/supabase.ts` — Supabase client (anon key — safe for Next.js)
- `dashboard/.env.local` — All env vars including GITHUB_REPO, PUBLISH_DRY_RUN

### Critical Architecture Rules

1. **Never use `SUPABASE_SERVICE_KEY` (sb_secret_* format) in Next.js route handlers on Windows** — `createClient` hangs forever. Use the anon key (`sb_publishable_*`) for reads, and spawn Python for all writes.
2. **All mutating actions spawn detached Python** — `spawn('python', ['run.py', '--action', slug], { detached: true, stdio: 'ignore' })` then `child.unref()`. Returns `{ success: true }` immediately.
3. **TinaCMS frontmatter must be exact** — only `title`, `description`, `date`, `tags`, `image`. No slug, author, excerpt, seo_keywords.
4. **Filename format** — `{slug}.mdx` (no date prefix). TinaCMS requires this for routing.
5. **No direct GitHub pushes from Render Agent** — Avoid keeping GitHub tokens natively inside Render. Use the custom `/api/agent/blog` endpoint directly on Buteforce-Site, authenticated via `AGENT_SECRET_KEY`.
6. **PUBLISH_DRY_RUN=true** in .env.local — set to `false` when ready to go live.

### Supabase Schema Notes

- `topics` table: `id, slug, title, status, tags, created_at, updated_at`
- `blog_posts` table: `id, topic_id, research_json, mdx_draft, mdx_final, word_count, published_url`
- **Required constraint**: `ALTER TABLE blog_posts ADD UNIQUE (topic_id);` — needed for upsert

### Site Integration

- The agent interacts with the live website via `POST` and `GET` requests to `https://buteforce.com/api/agent/blog` (or configured `SITE_API_URL`). 
- Research agent pulls live `/content/blog/` to evade duplicate content overlaps and extracts JSON summaries from `lib/data.ts` to uphold brand messaging.
- Publisher agent commits directly through the proxy endpoint. `ButeForce-Site` API uses `GITHUB_PUBLISH_TOKEN` to fulfill commit protocols on `buteforce-code/ButeForce-Site` repository.
- Remotion video generation is installed in `blog-agent/dashboard` for topic-based social assets. Use `npm run remotion:studio` to preview, `npm run remotion:render:sample` to test, and `npm run remotion:render:topic -- ...` with props generated by the topic detail page.

### Environment Variables (dashboard/.env.local)

```
GOOGLE_AI_API_KEY=...         # Gemini via Google AI Studio
GOOGLE_GENAI_USE_VERTEXAI=false
ADK_GEMINI_MODEL=gemini-2.5-flash
TAVILY_API_KEY=...
SUPABASE_URL=...
SUPABASE_ANON_KEY=...         # Safe for Next.js (sb_publishable_* format)
SITE_API_URL=https://buteforce.com/api/agent/blog
AGENT_SECRET_KEY=...          # Token syncing agent to website API
PUBLISH_DRY_RUN=true
```

---

## Known Issues / Watchlist

### Website (buteforce.com)
- `hero-poster.jpg` is missing (404) — does not affect functionality
- TinaCMS dev server occasionally requires Ctrl+C + restart if it freezes
- The `StaggerContainer` component wraps children in a `motion.div w-full h-full` which can break grid layouts — use it inside a separate grid wrapper, not as the grid itself (fixed 2026-04-07)

### Blog Agent
- **Vertex AI Execution Block**: Vertex AI throws 403/404 for Gemini prediction requests. Do NOT use Vertex AI. Always use Google AI Studio natively with `GEMINI_API_KEY` and `GOOGLE_GENAI_USE_VERTEXAI=false`, model `gemini-2.5-flash`.
- **Supabase service key hangs in Next.js on Windows**: `sb_secret_*` format key causes `createClient` to hang indefinitely in Next.js API routes on Windows. All DB mutations go through Python spawn. Only use `sb_publishable_*` (anon key) in Next.js.
- **Dev server TCP connections**: Excessive bash curl calls can create stuck ESTABLISHED connections on port 3005, overwhelming the dev server. Fix: Ctrl+C → `npm run dev`.
- **Swarm DB constraint** (fixed 2026-04-11): The `blog_posts` table requires `UNIQUE (topic_id)` for upserts to work. Already applied in Supabase.
- **PUBLISH_DRY_RUN**: Currently `true` in `.env.local`. Change to `false` when ready to push posts live to GitHub.
- **Free-tier Supabase auto-pause = dashboard blackout** (diagnosed 2026-05-28): The blog dashboard reads `topics` from Supabase project `mrfiusskqnnsjmfiffci` ("Marketing Agent Swarm"). On the free tier, Supabase pauses a project after ~7 days of no queries. While paused, `/api/topics` times out and the Render dashboard shows **no blogs** ("old blogs gone") — but buteforce.com/blog is unaffected because the live site serves committed MDX from a separate Vercel deploy. Fix: restore the project (Supabase MCP `restore_project` or the Supabase dashboard "Restore" button); it comes back `ACTIVE_HEALTHY` in ~2 min with all data intact. Prevention: hit the DB at least weekly (a cron/uptime ping to the dashboard `/api/topics`) or upgrade to a paid Supabase plan.
- **render.yaml Vertex flag mismatch** (open, noted 2026-05-28): `blog-agent/render.yaml` and `blog-agent/.env` set `GOOGLE_GENAI_USE_VERTEXAI=true`, which contradicts the Vertex AI Execution Block above and `dashboard/.env.local` (`false`). Dashboard listing is unaffected, but agent research/writing runs on Render will likely 403/404 until this is set to `false` (verify Imagen image-gen path first, since it may depend on Vertex creds).
