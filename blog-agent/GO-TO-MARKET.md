# Go-to-market readiness — Trolls

> State of the product against "can we sell this to someone who is not us".
> Updated **2026-07-28**. Every ✅ is verified against code in this repo; every ⬜
> is genuinely outstanding.

---

## Stage 1 — Safe to run on our own site

Everything here is done. This was the blocking set: the dashboard was fully
public against a pipeline with `PUBLISH_DRY_RUN=false`.

| | Item | Where |
|---|---|---|
| ✅ | Authentication on every page and API route, failing closed in production | `dashboard/middleware.ts`, `lib/auth.ts` |
| ✅ | Login rate limiting (5 / 5 min / IP) | `lib/ratelimit.ts` |
| ✅ | Per-run and per-day spend ceilings, checked before each agent call | `swarm/telemetry.py` |
| ✅ | Prompt-injection containment on operator feedback | `swarm/guards.py` |
| ✅ | RLS lockdown — anon read policies on `topics` / `blog_posts` dropped | `setup_db.py` |
| ✅ | `/api/track` validated, minimised, rate-limited | `app/api/track/route.ts` |
| ✅ | View-data pseudonymisation + retention + daily purge job | `lib/privacy.ts`, `.github/workflows/retention-purge.yml` |
| ✅ | Per-agent telemetry and a live swarm view | `swarm/telemetry.py`, `app/swarm/` |
| ✅ | Test coverage for the above | `tests/test_telemetry.py`, `tests/test_guards.py` |

### Deploy checklist

Host: `https://buteforce-blog-dashboard.onrender.com`

| | Step | Status |
|---|---|---|
| ✅ | Schema migration — `agent_runs`, `agent_events`, `blog_views.expires_at`, `purge_expired_views()` | Applied via Supabase MCP 2026-07-28 (project `mrfiusskqnnsjmfiffci`). `setup_db.py` is idempotent and reaches the same state if you prefer to run it. |
| ✅ | Code deployed | `bc8df4e` live. Verified: `POST /api/run` unauthenticated → `401 auth_not_configured` |
| ✅ | Anon RLS read policies dropped | Verified: anon reads 0 rows, service key reads 33 topics / 11 posts |
| ✅ | Retention live | A tracked view wrote `expires_at` at +90d, UA reduced to a family, no session id |
| ⬜ | **Set `DASHBOARD_PASSWORD` on Render** | Until set, the dashboard fails closed and nobody can sign in |
| ⬜ | **Set `AUTOPILOT_TICK_SECRET` on Render** | `/api/autopilot/tick` currently returns **503 "not configured"** — the hourly cron is not running |
| ⬜ | Add repo secret `PURGE_URL` = `https://buteforce-blog-dashboard.onrender.com/api/privacy/purge` | Daily retention purge |
| ⬜ | Run one topic and confirm `/swarm` shows the agents firing | Final smoke test |

> Rollback for the RLS drop, if the dashboard ever goes blank:
> ```sql
> CREATE POLICY anon_read_topics ON topics FOR SELECT USING (true);
> CREATE POLICY anon_read_blog_posts ON blog_posts FOR SELECT USING (true);
> ```

---

## Stage 2 — Sellable to a first external client

None of this is built. Each item is a real blocker, not a nice-to-have.

| | Item | Why it blocks |
|---|---|---|
| ⬜ | **Multi-tenancy** — tenant table, config out of files, per-tenant GEO registry | No tenant column exists anywhere. Brand config loads from disk, including a hardcoded `D:/Projects/...` fallback. One deployment = one brand. |
| ⬜ | **Per-tenant credential vault** | One `SITE_API_URL`, one `AGENT_SECRET_KEY`. |
| ⬜ | **Per-user identity + audit trail** | One shared password. "Who approved this post" is unanswerable. |
| ⬜ | **Signed DPA + subprocessor disclosure** | Required the moment we process a client's visitor data. Facts are in `PRIVACY.md` §5; the document does not exist. |
| ⬜ | **Content liability clauses reviewed by counsel** | `PRIVACY.md` §6 is engineering intent, not contract language. |
| ⬜ | **Breach-notification runbook** | DPDP and GDPR both require one. Not code, and not written. |
| ⬜ | **The GEO gate has never run for a non-Buteforce brand** | Its proof numbers, competitor registry and author are ours (`swarm/geo.py`). Untested assumption. |

---

## Stage 3 — Credibility, before we sell AI visibility

| | Item |
|---|---|
| ⬜ | **Fix our own 0/18 AI-visibility score.** Selling AI-visibility tracking while scoring zero on our own frozen prompt set is the first objection we will get. It is also the product demo. |
| ⬜ | **Measure real cost per post.** The instrumentation now exists; run enough posts through it to replace the estimates in `content_engine_features.md` §14 before pricing tiers. |
| ⬜ | **Decide the AI-disclosure position.** Byline or not — some clients' own policies will require it. |
| ⬜ | **Trademark search on "Trolls".** |

---

## Standing risks — manage, do not "fix"

**Google scaled content abuse.** Spam policies were confirmed on 15 May 2026 to
cover AI Overviews and AI Mode, and scaled content abuse applies regardless of
whether content is AI- or human-generated. Manual actions can remove a site from
results entirely. Our gates are the mitigation and they are genuinely stronger
than a generic pipeline's — but no supplier can warrant rankings, and no contract
we sign should imply one.

**Competitor comparison tables.** The GEO gate *requires* naming real rivals.
That is deliberate and it works for AI visibility. It also means auto-publishing
comparative claims about named companies on a client's domain. Keep the gate;
allocate the indemnity.

**Pricing is still unconfirmed.** No verified price list exists. Anything quoted
before Dhyan confirms is a guess with a number attached.
