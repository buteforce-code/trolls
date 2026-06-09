# Buteforce Blog Agent

Stateful, India-first AI pipeline for blog creation. State lives in Supabase; each stage is a
separate Google ADK agent run. Positioning: **Chennai's Industrial AI Company** — see
`config/positioning.md` and `config/seo-strategy.md` (the authoritative ICP + keyword strategy
every agent loads).

## Pipeline

```
queued → researching → verifying_research → writing → verifying_draft → publishing → published
```

Six agents plus a schema step:

1. **Research** — reads already-published posts + brand data, then Tavily (web/X/Reddit/LinkedIn/IG), YouTube, GitHub → structured JSON digest with an India-first `buteforce_angle` and a `target_keyword`.
2. **Writer** — digest → 1,400–2,000-word MDX, anti-fluff rules, India-first ICP, SEO keyword placement.
3. **Humaniser** — strips AI tells, rewrites in Dhyan's voice.
4. **Imager** — Imagen (Vertex AI) hero + inline images with a vision QA gate.
5. **Linker** — injects 2–4 contextual internal/external backlinks.
6. **Schema (JSON-LD)** — generates Article + FAQ structured data (`schema_ld.py`); also injects `image` + `faqs` into the MDX frontmatter so the live site renders BlogPosting + FAQPage rich results. Full graph persisted to `blog_posts.schema_json`.
7. **Social (`social.py`)** — repurposes the finished post into a LinkedIn + X kit (carousel, the 5 LinkedIn post types, company-page post, X threads, single tweets, hashtags), India-first in Dhyan's voice. Persisted to `blog_posts.social_json` and surfaced as copy-ready blocks on the dashboard topic page.
8. **Publisher** — POSTs the MDX to the site's secure API.

Two human approval gates (research, draft) with a rejection → re-run-with-feedback loop. Driven by
the Next.js dashboard (`dashboard/app/api/`) or the `run.py` CLI.

> **Publishing is a site-API POST, not a GitHub commit.** `swarm/tools/github_tool.py:github_publish()`
> POSTs to `SITE_API_URL` (default `https://www.buteforce.com/api/agent/blog`) with a Bearer
> `AGENT_SECRET_KEY`, preserving method + body across redirects. `github_search()` is the only part
> that talks to the GitHub API. There is no `GITHUB_REPO` requirement.

## Local run

Prerequisites: Node 20+, Python 3.10+.

```powershell
cd blog-agent
python -m pip install -r requirements.txt
cd dashboard
npm ci
```

Environment:

- Copy `.env.example` to `.env` in `blog-agent/` and set: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_URL`, `ADK_GEMINI_MODEL`, Tavily/YouTube/GitHub keys, and (for live publish) `AGENT_SECRET_KEY` + `SITE_API_URL`.
- Copy `.env.example` to `dashboard/.env.local` (or map only required keys).

Database:

```powershell
python setup_db.py        # idempotent schema bootstrap (topics, blog_posts, columns, RLS)
python seed_topics.py     # seed the 24-post India-first roadmap as queued topics
python seed_topics.py --dry-run   # preview the roadmap without writing
```

Start dashboard:

```powershell
cd blog-agent/dashboard
npm run dev
```

Dashboard endpoints: `POST /api/run`, `POST /api/approve`, `POST /api/reject`, `GET /api/topics`, `GET /api/topic/:slug`.

CLI:

```powershell
python run.py --topic "..." --tags "computer-vision,manufacturing,india"   # start + research
python run.py --approve <slug>                                             # advance the current gate
python run.py --reject  <slug> --feedback "..."                            # re-run the stage with feedback
python run.py --list                                                       # all topics + statuses
```

## Production notes

- Dashboard API routes spawn `python run.py`; the deploy target must support both Node and Python in one runtime.
- Never expose `SUPABASE_SERVICE_KEY` to browser code.
- `PUBLISH_DRY_RUN=true` is the default — nothing auto-publishes until `AGENT_SECRET_KEY` is set and the flag is flipped to `false`.
- Runtime visibility: `run.py` runs on the server, so raw stdout/stderr appears in server/Render logs, not the browser console. The dashboard surfaces status changes and `last_error` in-app.

## Render

Use the blueprint in `render.yaml`. Health check: `/`.
