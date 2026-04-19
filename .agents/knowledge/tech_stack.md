---
links: "[[INDEX]] | [[dhyan_psychology]] | [[founder]] | [[brand_bible]] | [[marketing_engine]]"
type: technical
last-updated: 2026-04-15
---

# Tech Stack — Buteforce Systems

> All conventions here align with [[dhyan_psychology#Decision Making Principles]] — always custom, never generic.
> Brand design tokens that inform the code → [[brand_bible#Website Design Language]].

## Website (buteforce.com)

| Layer | Technology | Notes |
|---|---|---|
| Framework | Next.js 15 (App Router) | React 19, latest stable |
| Styling | TailwindCSS v3 | Custom design tokens, dark-only |
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
| Claude API | LLM reasoning tasks |
| Mistral | Lightweight LLM for classification |
| OpenAI API | Embeddings and GPT tasks |
| Google Gemini (ADK) | Primary reasoning engine for autonomous agents (`gemini-2.5-flash`) via Google AI Studio |
| Telegram Bot API | Real-time operation notifications |
| n8n | Workflow automation (some pipelines) |

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
