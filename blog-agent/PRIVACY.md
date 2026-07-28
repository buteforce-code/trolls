# Data handling — Trolls

> Engineering reference for what personal data this system touches, where it
> goes, and how long it stays. It is the factual input to a customer-facing
> privacy policy and DPA — **it is not itself a legal document, and the
> contractual language in §6 has not been reviewed by counsel.**
>
> Last verified against the code: **2026-07-28**.

---

## 1. What personal data exists

Only one table holds personal data: `blog_views`, written by `/api/track` when
someone reads a published post.

| Column | What it is | Treatment |
|---|---|---|
| `slug`, `path` | Which post was read | Validated against a strict pattern; not personal on its own |
| `referrer` | Where the reader came from | **Query string stripped** — origin + path only, so campaign/click ids are discarded |
| `ua` | Browser | **Reduced to a family** (`Chrome`, `Safari`, `bot`, `other`). The full fingerprint is never stored |
| `session_id` | Repeat-visit signal | **Keyed SHA-256 digest**, truncated to 128 bits. Without `VIEW_HASH_SALT` it is dropped entirely rather than stored as a weak hash |
| `viewed_at`, `expires_at` | When, and when it dies | — |

We do **not** store IP addresses, and we set no cookies on the published blog.
The client's own analytics may — that is their processing, not ours.

`agent_runs` / `agent_events` hold operational telemetry (agent names, token
counts, durations, gate verdicts). No visitor data.

---

## 2. Retention

Every row is written with an `expires_at` of `now() + VIEW_RETENTION_DAYS`
(default 90, hard-capped at 400 in `lib/privacy.ts` — configuration cannot opt
out of having a limit).

`POST /api/privacy/purge` deletes expired rows, and also deletes pre-migration
rows with a `NULL` expiry on their own age so nothing is retained indefinitely.
It runs daily via `.github/workflows/retention-purge.yml` and fails the workflow
loudly if it errors.

> A retention policy with no delete job is the thing a regulator finds. This one
> deletes.

---

## 3. Legal basis and roles

| Scenario | Our role | Their role |
|---|---|---|
| buteforce.com (our own blog) | Data Fiduciary / Controller | — |
| A client's site we publish to | Data Processor | Data Fiduciary / Controller |

When serving a client we process visitor data **on their instructions**, which
means a signed DPA is required before onboarding — see §6.

---

## 4. Data subject rights

Because `session_id` is a keyed digest with no lookup table, we generally
**cannot identify a data subject** from view data. Under GDPR Art. 11 that
removes the obligation to acquire additional data purely to enable identification.

What we can do:

- **Erasure of a whole site's data** — delete by `slug`; supported today.
- **Access/portability** — the client can export their own aggregate stats.
- **Individual erasure** — not possible by design, because the data is
  pseudonymised. This must be stated in the privacy policy rather than promised
  and then not delivered.

---

## 5. Subprocessors

Any of these that process content or data on our behalf must be disclosed to
clients before onboarding, and re-disclosed when the list changes.

| Subprocessor | Purpose | Data | Location |
|---|---|---|---|
| OpenAI | Content generation, image generation, vision QA | Prompts, research digests, drafts | US |
| Tavily | Web/social research | Search queries | US |
| Google (YouTube Data API) | Research signal | Search queries | US |
| GitHub | Repository search; CI cron | Search queries | US |
| Supabase | Database, storage | All pipeline data incl. `blog_views` | Region of the project |
| Render | Application hosting | Runtime, logs | Region of the service |

Two things to confirm before selling outside India:

1. **Transfer mechanism** for EU/UK personal data reaching US subprocessors
   (Standard Contractual Clauses, or reliance on each vendor's DPF status).
2. **Data residency**, if a client requires India-resident storage — Supabase and
   Render regions are configurable, the LLM vendors are not.

---

## 6. Contract clauses this system requires — DRAFT, NEEDS COUNSEL

These follow directly from how the product works. **Wording below is engineering
intent for a lawyer to draft from, not usable contract language.**

1. **Content sign-off.** The client is the publisher of record. Autopilot's
   24-hour veto window is the review mechanism; if they disable review, they
   accept publication as approved. *(Basis: a post has already shipped with
   statistics attributed to Unilever and Nestlé that no source supported — see
   `README.md`. The auditor and GEO gates reduce that risk; they do not remove
   it.)*

2. **Comparative claims.** The GEO gate **requires** every post to name at least
   two real competitors in a comparison table with a "where they win" column.
   Comparative advertising is lawful in India; disparagement is not. The client
   must accept that named-competitor comparisons will be published on their
   domain, and indemnity for claims arising from them needs explicit allocation.

3. **Search-engine risk.** Google's spam policies were confirmed on 15 May 2026
   to cover AI Overviews and AI Mode, and scaled content abuse applies
   *regardless of whether content is AI- or human-generated*. Manual actions can
   remove a site from results. Our gates are the mitigation; no supplier can
   warrant rankings, and the contract must not imply one.

4. **Generated imagery.** Off by default (`ENABLE_IMAGES=false`). If enabled,
   check the image vendor's current terms and indemnity posture before use on a
   client domain.

5. **AI disclosure.** Decide once, deliberately: does published content carry an
   AI-assisted byline? Some clients' own policies will require it.

---

## 7. Regulatory clock

- **DPDP Act 2023** — Rules notified 13 Nov 2025. Full compliance **13 May 2027**.
  Soft enforcement is widely expected to end around **November 2026**. As a Data
  Fiduciary we need notice, a consent basis, retention limits (§2 ✅), breach
  reporting, and a rights workflow (§4).
- **GDPR** — applies if we sell into the EU/UK. Requires a DPA per client, the
  subprocessor list in §5, and a transfer mechanism.

**Open, unresolved:** breach-notification runbook. There is no documented
procedure for detecting, assessing and reporting a personal-data breach within
the required window. That is a real gap and it is not code.
