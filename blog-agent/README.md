# Buteforce Blog Agent

Stateful, India-first AI pipeline for blog creation. State lives in Supabase; each stage is a
separate Google ADK agent run. Positioning: **Chennai's Industrial AI Company** — see
`config/positioning.md` and `config/seo-strategy.md` (the authoritative ICP + keyword strategy
every agent loads).

## Pipeline

```
queued → researching → verifying_research → writing → verifying_draft → publishing → published
```

Seven agents plus a schema step:

1. **Research** — reads already-published posts + brand data, then Tavily (web/X/Reddit/LinkedIn/IG), YouTube, GitHub → structured JSON digest with an India-first `buteforce_angle` and a `target_keyword`.
2. **Audit** (`auditor.py`) — quality + fact gate run right after research: checks key facts are backed by the source signals, the SEO target is coherent, the angle is non-obvious + India-first, dedup risk vs already-published, and ICP fit. Verdict (`passed`/`score`/`recommendation`) is stored in `blog_posts.audit_json` and surfaced at the research-review gate. In autopilot a `reject` triggers one automatic re-research; a second reject holds the topic for human review instead of writing.
3. **Writer** — digest → 1,400–2,000-word MDX, anti-fluff rules, India-first ICP, SEO keyword placement.
4. **Humaniser** — strips AI tells, rewrites in Dhyan's voice.
5. **Imager** — OpenAI image generation (dall-e-3) hero + inline images with a gpt-4o vision QA gate. **Off by default** (`ENABLE_IMAGES=false`); when off, posts publish text-only.
6. **Linker** — injects 2–4 contextual internal/external backlinks.
7. **Schema (JSON-LD)** — generates Article + FAQ structured data (`schema_ld.py`); also injects `image` + `faqs` into the MDX frontmatter so the live site renders BlogPosting + FAQPage rich results. Full graph persisted to `blog_posts.schema_json`.
8. **Social (`social.py`)** — repurposes the finished post into a LinkedIn + X kit (carousel, the 5 LinkedIn post types, company-page post, X threads, single tweets, hashtags), India-first in Dhyan's voice. Persisted to `blog_posts.social_json` and surfaced as copy-ready blocks on the dashboard topic page.
9. **Publisher** — POSTs the MDX to the site's secure API.

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

- Copy `.env.example` to `.env` in `blog-agent/` and set: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_URL`, `OPENAI_API_KEY` (provider defaults to `LLM_PROVIDER=openai`, model `OPENAI_MODEL=gpt-4o`), Tavily/YouTube/GitHub keys, and (for live publish) `AGENT_SECRET_KEY` + `SITE_API_URL`.

> **LLM provider.** The swarm runs on OpenAI (`gpt-4o`) via ADK's `LiteLlm` wrapper — see `swarm/llm.py`. All eight agents share one model. To fall back to Gemini, set `LLM_PROVIDER=gemini` and the `ADK_GEMINI_MODEL` / Google keys. Image generation is opt-in: `ENABLE_IMAGES=true` (+ `OPENAI_IMAGE_MODEL`, default `dall-e-3`).
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

### Catch-up: write the whole queue now (`produce-all`)

To clear a backlog (e.g. a pile of `queued` topics after downtime) without waiting one
tick per day, fire the one-shot catch-up. It researches + audits + writes **every**
queued topic immediately and schedules them on the cadence; the hourly tick then drips
them out. Published posts are untouched.

```bash
curl -X POST https://<your-render-host>/api/autopilot/produce-all \
  -H "Authorization: Bearer $AUTOPILOT_TICK_SECRET"
```

Or locally: `python run.py --produce-all`. Bounded by `PRODUCE_ALL_MAX` (default 200).

> **On a 512 MB Render instance, prefer the hourly tick over produce-all.** Each tick
> writes **one** queued topic in a short-lived process that exits and frees its memory,
> whereas produce-all writes the whole backlog in one long-lived process and can exceed
> 512 MB (OOM). The tick now drains the seeded backlog one-per-tick (publishing still
> drips 1/day), so on a small instance just let the cron run — the queue clears in about
> a day. Use produce-all only on ≥1 GB instances.

## Analytics

`/stats` (linked from the dashboard header) shows pipeline status, publishing cadence,
content quality (avg words, audit score, research confidence, schema/social/hero
coverage), top tags, the upcoming auto-publish schedule, and **blog views**.

### View tracking

Real views are recorded by `POST /api/track` (CORS-open) into the `blog_views` table
(service-key only; not publicly readable). Add this once to the **published blog post
template** on the live site so every view is counted:

```html
<script>
  fetch("https://<your-render-host>/api/track", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slug: "<post-slug>", path: location.pathname, referrer: document.referrer }),
    keepalive: true,
  }).catch(() => {});
</script>
```

No-JS fallback: `<img src="https://<your-render-host>/api/track?slug=<post-slug>" width="1" height="1" alt="">`.
Until the snippet is live the analytics page shows content/pipeline stats and 0 views.

## Render

Use the blueprint in `render.yaml`. Health check: `/`.
