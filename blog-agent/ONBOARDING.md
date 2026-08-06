# Client onboarding — the intake that produces a BrandProfile

> Design spec, **not yet built**. The profile layer it feeds (`swarm/brand.py`,
> `profiles/*.json`) is built and tested. Written 2026-08-04 for review before implementation.

---

## The one idea this rests on

**The GEO gate is the intake specification.** Don't design a brand questionnaire and hope the
content engine can use the answers. Read `swarm/geo.py`, list what a post must contain to
publish, and collect exactly that — nothing else is required, and nothing on that list is
optional.

| The gate demands | So the intake must extract | Fails as |
|---|---|---|
| ≥2 unrounded proof numbers | Real delivered metrics **with provenance** | "We're highly accurate" |
| ≥2 named real competitors | Who this buyer actually compares them against | "We have no real competition" |
| A "not a fit if…" section, ≥40 words | Who they turn away, and when a rival wins | "We can help anyone" |
| A named author with a stable `@id` | One real person, one spelling, one URL | "The team" |
| Zero puffery adjectives | Specifics in place of every adjective | "World-class, cutting-edge" |

`BrandProfile.validate()` already enforces the machine-checkable half. A tenant whose evidence
cannot satisfy its own thresholds raises at load:

```
Brand profile 'thin' is not publishable:
  - 1 proof point(s) supplied but the gate demands 2 in every post. A post cannot pass.
  - 1 competitor(s) supplied but every post must name 2 in a comparison table.
```

**That error is the onboarding completion check.** Not a form's "submit" button — an assertion
that this client can actually be published for. It is worth saying out loud to a prospect: if
we cannot fill this in, we cannot make you citable, and neither can anyone else.

---

## Three tracks, because they fail in different ways

### Track 1 — Facts (structured form, ~20 min)

Straight capture. NAP, canonical name and its exact spelling, author identity, service list,
locale. Boring, and the only track where a form is the right instrument.

One rule: **every number needs a source field, and "marketing" is not a source.** This is
enforced in code — a proof point with a blank `source` is refused. On 2026-07-29 this pipeline
published invented Unilever and Nestlé statistics inside `FAQPage` schema. Under a client's
domain that is their liability, not ours.

### Track 2 — Stances ("his view on things")

The differentiator, and the part a form cannot collect. Asking "what makes you different?"
returns the same four adjectives from every company on earth. Opinions are what make a page
quotable rather than skippable — an answer engine cannot quote a vibe.

**Instrument: a forced-choice opinion battery.** Present 12–15 contested statements from their
category. They pick a side and say why in one sentence. Contested is the whole point — if
everyone in the industry agrees, the answer carries no information.

> *"Most factories buying vision systems should buy a Cognex sensor, not a custom build."*
> — Agree / Disagree / It depends → **and one sentence on why.**

Three things fall out of one exercise: their genuine positions, the vocabulary they naturally
use (Track 3 input), and the disagreements that become question-form H2s.

**Then the disqualification interview** — the hardest questions, asked by a human, because
nobody answers these well in a text box:

1. Describe the last client you turned down. Why?
2. Name a competitor who is genuinely better than you at something. What?
3. What do you get complained about, fairly?
4. Below what deal size does this stop making sense for you?
5. What do buyers assume you do that you don't?

Answers 1–4 become the "not a fit if…" section on every post. Answer 5 usually corrects the
positioning. Expect resistance; the resistance is the signal. A client who cannot name one
thing a competitor does better will approve brochure copy and then wonder why nothing gets
cited.

### Track 3 — Voice (derived, never declared)

Do **not** ask "describe your brand voice." You get "professional yet approachable" from
everyone, and it constrains nothing.

Ingest 5–10 real artefacts they already wrote — site copy, LinkedIn posts, a sales email, a
support reply, a founder essay — and derive the profile from those: sentence length
distribution, hedging vs. assertion, jargon tolerance, first person singular vs. plural,
whether they use humour and where. The `brand-voice` skill (`~/.claude/skills/brand-voice/`)
does exactly this from supplied samples.

Then show them the derived profile and let them correct it. Reacting to a draft is a task
people are good at; describing themselves cold is one they are not.

**Edge case worth pricing:** a client with no usable writing samples. That is not a blocker,
it is a different engagement — voice has to be *created* with them, which is a workshop, not
an intake. Catch it in qualification, not in week two.

---

## What comes out

```
profiles/<slug>.json      Tracks 1 + 2 → structured facts, proof points w/ provenance,
                          competitors, author identity, thresholds
config/<slug>/            Tracks 2 + 3 → positioning.md, icp.md, voice.md,
                          founder.md, seo-strategy.md
```

Both are already wired: `brand.load(slug)` reads the first, `brand_context.py` resolves the
second with per-tenant directories and refuses to fall back to another brand's positioning.

---

## Decisions needed before this gets built

1. **Who runs the disqualification interview?** It needs a human who will push back. If it is
   always Dhyan, onboarding does not scale past a handful of retainers and that is a real
   constraint on the retainer model — worth knowing now, not at client six.
2. **Does the client approve their own profile?** Recommend yes, in writing. They are
   asserting these numbers publicly under their own domain; the sign-off is also the
   indemnity conversation that `GO-TO-MARKET.md` flags for competitor comparison tables.
3. **Self-serve or assisted?** The form half (Track 1) can be self-serve. Tracks 2 and 3
   cannot, today. A self-serve signup that produces a thin profile produces a tenant that
   cannot publish — the validator will say so, but only after they have signed up.
4. **How often does a profile get re-derived?** Positioning drifts. Buteforce's own
   positioning ran unchanged and wrong for two months (see `config/positioning.md` header).
   A retainer should include a scheduled profile review.

---

## Not yet built, in dependency order

- [ ] `tenants` table; `tenant_id` on `topics`, `blog_posts`, `agent_runs`, `blog_views`
- [ ] **`topics.slug` is `UNIQUE` globally** (`setup_db.py:20`) — two clients wanting the same
      slug collide today. Must become `UNIQUE (tenant_id, slug)`. Cheap now, painful later.
- [ ] RLS policies scoped per tenant
- [ ] `users` + membership; per-user identity replacing the single `DASHBOARD_PASSWORD`
      (`dashboard/lib/auth.ts` — "there is one operator, so a session store would be
      ceremony" is no longer true). This also closes the "who approved this post" audit gap.
- [ ] Per-tenant credential vault — one `SITE_API_URL` and one `AGENT_SECRET_KEY` today
- [ ] Signup flow → intake → profile draft → validation → activation
