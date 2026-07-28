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

### Deploy checklist — do these before the next Render deploy

1. `python setup_db.py` — creates `agent_runs`, `agent_events`, adds
   `blog_views.expires_at`, **drops the anon read policies**. Idempotent.
2. Set `DASHBOARD_PASSWORD` on Render. `APP_SECRET` and `VIEW_HASH_SALT` are
   `generateValue: true` and will be created automatically.
3. Add repo secret `PURGE_URL` = `https://<render-host>/api/privacy/purge`.
4. Deploy, then confirm: visiting the dashboard redirects to `/login`, and
   `curl -X POST https://<host>/api/run` returns **401**.
5. Run one topic and confirm `/swarm` shows the agents firing.

> ⚠️ Step 1 drops the anon policies. Anything reading these tables with the anon
> key will stop working. Nothing in this repo does — all dashboard reads go
> through server routes on the service key — but check any external consumer first.

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
