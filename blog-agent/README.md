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

## Autopilot (autonomous mode)

Autopilot drains the queued roadmap and then keeps the blog alive on its own — no
clicks. It auto-advances research → writing (the two human gates are skipped), then
holds each finished post in a **`scheduled`** state with a `scheduled_for` timestamp:
a **24-hour veto window** where the post auto-publishes at its slot *unless* you reject
it first in the dashboard. Cadence (default **1 post / 24h**) is enforced by those
timestamps, so the trigger can fire on a coarse schedule.

```
queued → researching → verifying_research → writing → verifying_draft → SCHEDULED → published
            (auto)            (auto)          (auto)        (auto)        (24h veto)   (at slot)
```

When the queue empties, the **ideator agent** (`swarm/agents/ideator.py`) researches the
brand + live market and generates a fresh batch of India-first topics, so the engine
never runs dry.

**One tick** (`swarm/autopilot.py:run_tick`) does, idempotently:
1. publish the single most-overdue `scheduled` post (re-spacing any backlog so downtime
   never dumps everything at once);
2. keep `AUTOPILOT_BUFFER` finished posts scheduled ahead (research + write the next
   topic, then schedule it at the next free slot);
3. refill the queue via the ideator when nothing is left.

### How it fires

A free **GitHub Actions** cron (`.github/workflows/blog-autopilot.yml`, hourly) POSTs to
the dashboard's secret-protected `POST /api/autopilot/tick`, which spawns
`python run.py --autopilot` on Render and returns immediately. You can also run a tick by
hand: `python run.py --autopilot`, or trigger the workflow from the Actions tab.

### One-time setup checklist

1. **DB migration** — apply the new `scheduled_for` column: `python setup_db.py` (idempotent).
2. **Render env** (already in `render.yaml`): confirm `PUBLISH_DRY_RUN=false`,
   `AGENT_SECRET_KEY` set, and set **`AUTOPILOT_TICK_SECRET`** to a long random string.
   Tune `PUBLISH_GAP_HOURS` / `AUTOPILOT_ENABLED` as desired.
3. **GitHub repo secrets** (Settings → Secrets and variables → Actions):
   - `AUTOPILOT_URL` = `https://<your-render-host>/api/autopilot/tick`
   - `AUTOPILOT_TICK_SECRET` = the same value as the Render env var.
4. Redeploy. The hourly cron takes over from there. Pause anytime with
   `AUTOPILOT_ENABLED=false` (no redeploy needed) or by disabling the workflow.

### Vetoing a post

Open the scheduled post in the dashboard before its slot: **Publish Now** ships it
immediately, **Send Feedback** pulls it off the schedule and re-drafts it with your notes
(it won't auto-publish again — it returns to manual review), and **Delete** drops it.

## Render

Use the blueprint in `render.yaml`. Health check: `/`.
