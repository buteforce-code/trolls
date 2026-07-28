# Security posture — Trolls

> Written to be handed to a prospect's security reviewer. It describes what the
> code actually does, not what we intend. Where a control is missing it says so.
>
> Last verified against the code: **2026-07-28**.

---

## Authentication

Every dashboard page and API route is gated by `dashboard/middleware.ts`.

| Surface | Control |
|---|---|
| All pages, `/api/run`, `/api/approve`, `/api/reject`, `/api/delete`, `/api/reset`, `/api/topics`, `/api/topic/*`, `/api/stats`, `/api/swarm/*` | Signed session cookie (HMAC-SHA256, 12h TTL) |
| `/api/autopilot/tick`, `/api/autopilot/produce-all` | Bearer token (`AUTOPILOT_TICK_SECRET`) — the cron cannot hold a browser session |
| `/api/privacy/purge` | Bearer token *or* an authenticated session |
| `/api/track` | Public by necessity (called cross-origin by the published blog). Validated, minimised and rate-limited. Inserts a view row and nothing else. |
| `/login`, `/api/login`, `/api/logout` | Public — the way in |

**Fails closed.** With `APP_SECRET` or `DASHBOARD_PASSWORD` unset, production
returns 401 for every protected route. Development is allowed through with a
logged warning so `npm run dev` needs no secrets. There is no configuration in
which production runs open.

**Session tokens** are stateless HMAC over `{sub, exp}`, verified with a
length-independent constant-time comparison (`dashboard/lib/auth.ts`).
Cookies are `httpOnly`, `sameSite=lax`, and `secure` in production.

**Known limitation.** Sign-out clears the cookie but cannot revoke a token that
was already copied; a stolen token stays valid until `exp` (max 12h). Accepted
deliberately for a single-operator deployment. Rotating `APP_SECRET` invalidates
every outstanding token immediately, and is the break-glass procedure.

---

## Rate limiting

| Endpoint | Limit |
|---|---|
| `/api/login` | 5 attempts / 5 min / IP |
| `/api/track` | 60 requests / min / IP |

In-process fixed window (`dashboard/lib/ratelimit.ts`), bounded to 10,000 tracked
keys so the limiter cannot itself become a memory-exhaustion vector. **This is
per-instance and resets on redeploy** — effective on the current single-instance
Render deployment, and it must move to Postgres or Redis before running multiple
instances.

---

## Spend controls

An unauthenticated pipeline trigger made unbounded LLM spend a one-request
attack. Three ceilings now sit in front of every model call, checked *before* the
call rather than after (`swarm/telemetry.py`):

- `MAX_RUN_COST_USD` — default $3.00 per pipeline run
- `MAX_DAILY_COST_USD` — default $25.00 across all runs in a rolling 24h
- `MAX_RUN_TOKENS` — default 400,000 tokens per run

The token ceiling is a **backstop, not a duplicate**. An unpriced model — reached
by a model-name typo or a provider version bump — costs $0 by this module's
arithmetic, which would make both USD ceilings silently inert. Tokens are counted
regardless of price, so that ceiling still binds. An unpriced model also logs a
warning once per process.

Exceeding any of them raises `SpendCeilingExceeded`, which fails the run and
records it. `0` disables a ceiling; that is a deliberate opt-out, not the default.

Image generation does not go through the agent runner, so it is metered
separately from what the imager returns (`orchestrator.py`) — otherwise the most
expensive module in the system would have been the one that spent invisibly.

Scope: `MAX_RUN_COST_USD` is per *run*, and autopilot opens one run per topic, so
a catch-up batch is bounded per post rather than in aggregate. The daily ceiling
is read once when a run opens, so concurrent processes can jointly overshoot it
by up to one per-run ceiling each. Acceptable at current concurrency (the cron is
serialised by a GitHub Actions concurrency group); it needs a transactional
counter before running parallel workers.

Cost is derived from a **list-price table captured 2026-07-28**
(`DEFAULT_PRICES`), overridable per model via `LLM_PRICE_OVERRIDES`. It is
accurate enough to bound spend and compare agents. **It is not billing-grade and
must not be quoted to a client as their cost.**

---

## Prompt injection

`/api/reject` accepts free-text feedback and passes it to the agent that writes
to the live site. Two layers (`swarm/guards.py`):

1. **Sanitised** — bounded to 2,000 characters; leading markdown headings
   stripped; control characters removed; line endings normalised. Delimiter runs
   are neutralised so a forged prompt section cannot be constructed — including
   the three variants that defeat the naive "three identical adjacent
   characters" rule and were demonstrated against an earlier version of this
   guard: **spaced** (`= = = SYSTEM = = =`), **mixed** (`=-=-=`), and **Unicode
   look-alikes** (fullwidth `＝`, box-drawing `─━═`, em/en dashes).
2. **Fenced** — wrapped in explicit BEGIN/END markers labelled untrusted, with a
   stated precedence rule telling the model the block cannot change its role,
   output format, brand rules or quality requirements.

The stance is containment, not detection. We do not try to recognise every
phrasing of "ignore previous instructions"; we remove the structure that would
give such text authority. Covered by `tests/test_guards.py`, which pins each of
the bypasses above as a regression test.

Both rejection paths are covered. Feedback given at the research gate previously
reached no prompt at all — it was stored and then discarded — so the containment
was only ever exercised on the draft gate. Fixed; `run_research` now takes and
fences feedback the same way the writer does.

**Residual risk.** A determined injection may still influence *tone or topic*
within a single post. The GEO gate, length gate, auditor and link validator all
run afterwards on the produced text, so structural and factual requirements are
enforced regardless of what the feedback said. Publishing remains reversible.

---

## Command execution

Dashboard routes spawn `python run.py` via `child_process.spawn` with an
**argument array, never a shell string** (`dashboard/lib/python.ts`), so user
input cannot inject shell metacharacters. Slugs are validated against
`^[a-z0-9][a-z0-9-]{0,79}$` before reaching a filesystem path.

---

## Data access

- `topics` and `blog_posts` have RLS enabled with **no policies** — the previous
  `FOR SELECT USING (true)` anon policies were dropped. Anyone holding the anon
  key (a key that is public by design) could previously read every unpublished
  draft, research digest and audit verdict.
- `blog_views`, `agent_runs`, `agent_events` have RLS enabled with no policies.
- All dashboard reads go through server-side routes using the service key, which
  bypasses RLS. `SUPABASE_SERVICE_KEY` has no `NEXT_PUBLIC_` prefix and is never
  shipped to the browser.

---

## Secrets

- `.env*` is gitignored. `git log --all` confirms **no `.env`, key or credential
  has ever been committed**, including during the period the repository was
  public (until 2026-06-12).
- `APP_SECRET` and `VIEW_HASH_SALT` use `generateValue: true` in `render.yaml`,
  so they are generated by the platform rather than pasted by a human.

---

## Not yet built — say this plainly to a prospect

| Gap | Impact |
|---|---|
| **No multi-tenancy.** No tenant column on any table; brand config loads from files on disk. | One deployment serves exactly one brand. A second client needs a second deployment. |
| **Single operator account.** One shared password, no per-user identity, no audit trail of who approved what. | Not suitable where "who published this" must be answerable. |
| **No MFA.** | Password is the only factor. |
| **Distributed rate limiting.** | Blocks horizontal scaling. |
| **No penetration test.** | No third-party assurance has been obtained. |

---

## Reporting

Email `dhyan.vrit@gmail.com`. There is no bug bounty. We aim to acknowledge
within 3 working days.
