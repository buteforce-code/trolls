# Design Brief — Trolls Control Plane

> Trolls is Buteforce's marketing agent swarm (product name). The content it ships serves the
> Buteforce brand — see §3.

> Paste this whole file into a design session. It is self-contained: everything about the
> product, the user, the data, and the states is here. No repo access needed.

---

## 1. What this thing is

An autonomous blog engine writes and publishes SEO posts for **Buteforce** without a human in
the loop. Eight AI agents run in sequence — research → audit → write → humanise → link →
structured data → social kit → publish. It ships roughly **one post per day, forever**.

This app is **not** the blog. It is the **control plane**: the single window a founder opens to
see what the machine is doing and to stop it before it does something embarrassing.

Think air-traffic control, not CMS. The content already exists and is already good. The
question this UI answers is *"is the machine healthy, and is anything about to go out that
shouldn't?"*

## 2. Who uses it

**Exactly one person.** Dhyan, the founder. Technical. Time-poor. Opens this on a phone between
meetings, and on a desktop maybe twice a week.

There is no multi-user, no roles, no onboarding, no empty-state hand-holding for newcomers. The
user knows exactly what everything means. Optimise for **fast recognition by an expert**, not
explanation to a novice. Density is a feature.

The two questions the design must answer in under three seconds:

1. **Is anything broken?** (a stage failed, the engine has gone quiet, a post errored)
2. **Is anything about to publish that I want to kill?** (the veto window — see §5)

Everything else is secondary.

## 3. Brand

**Buteforce — Chennai's Industrial AI Company.** Precision AI systems for India's manufacturing
corridor: computer vision for quality control, retail analytics, document AI. Deployed on real
factory floors, not demos.

Audience for the *company* is CTOs and plant heads at Indian manufacturers. That matters here
only as tone: this is an **industrial instrument**, not a SaaS marketing dashboard. It should
feel like something mounted in a control room — precise, legible, unfussy, slightly severe.
Confident without decoration.

Existing brand marks: a black/near-black wordmark with a sharp geometric leaf/bolt glyph, and an
acid/electric yellow-green as the accent. The current build uses that yellow as the active-state
colour. Keep the accent disciplined — it should mean "attention here", never "decoration".

## 4. The pipeline (the core mental model)

Every post moves through these states in order. **This progression is the spine of the whole
interface.** A user should always be able to tell, at a glance, where a post sits on it.

```
queued → researching → verifying_research → writing → verifying_draft → scheduled → published
                                                                            ↓
                                                                      (24h veto window)
```

Plus `failed`, which can happen at any stage.

What each state means, and how urgent it is:

| Status | Meaning | Urgency |
|---|---|---|
| `queued` | Waiting its turn. **Normal resting state — can sit for days.** | None. Must NOT look alarming. |
| `researching` | Agent gathering sources. Takes minutes. | None, but show it's live. |
| `verifying_research` | Audit gate. Usually auto-passes; if held here twice, it needs a human. | Medium — may need a decision. |
| `writing` | Writer + humaniser + linker running. Takes ~20 min. | None, but show it's live. |
| `verifying_draft` | Draft gate. | Medium. |
| `scheduled` | **Finished. Auto-publishes at its timestamp unless vetoed.** | **HIGHEST — this is the money state.** |
| `published` | Live on the site. | None — archive. |
| `failed` | A stage crashed. `last_error` holds the reason. | High — needs action. |

Design note: the single most common failure of a dashboard like this is treating all eight
states as eight equal chips of different colours. They are not equal. `scheduled` and `failed`
are the only two that ever need the user to *do* something. `queued` is by far the most common
and least interesting. Weight the visual hierarchy accordingly.

## 5. The critical moment: the veto window

When a post finishes writing, it does **not** publish immediately. It enters `scheduled` with a
`scheduled_for` timestamp roughly 24 hours out. During that window the user can:

- **Publish now** — ship it immediately, skip the wait
- **Send feedback** — pull it off the schedule and re-draft with notes (returns to manual review, will not auto-publish again)
- **Delete** — drop it entirely

If they do nothing, **it goes live automatically.** Silence is consent.

This is the highest-stakes interaction in the product and it is currently buried. A scheduled
post with four hours left should be impossible to miss — a live countdown, prominent placement,
unambiguous "this is going out unless you act". Consider whether the dashboard should lead with
a dedicated "going out next" region above the general grid, rather than making the user hunt for
a yellow chip among forty cards.

## 6. Screens

### 6.1 Dashboard (`/`) — the main grid

Currently a flat, uniform grid of topic cards. Every card is the same size regardless of whether
it's a dead published post from March or something publishing in three hours. That flatness is
the core design problem to solve.

Each topic card carries:
- `title` — the post headline (the primary identifier)
- `status` — one of the eight above
- `slug` — URL-safe path, shown in monospace
- `tags` — 2–5 short keyword chips (`chennai`, `computer-vision`, `manufacturing`, `india`)
- `updated_at` — rendered as relative time ("4d ago", "20d ago")
- `scheduled_for` — only on scheduled posts; the auto-publish moment
- a dismiss/delete affordance

Also needs: a way to add a new topic manually, a link to analytics, and some always-visible
indication of **engine health** — when did the worker last run successfully? A control plane
whose own heartbeat is invisible is how you end up not noticing it died 41 days ago.

Realistic scale: 40–100 topics, growing indefinitely. Most will be `published` or `queued`.
Filtering, grouping, or collapsing by status is probably necessary — the design should have a
point of view on how a user finds the three cards that matter among ninety that don't.

### 6.2 Topic detail (`/topic/[slug]`)

The deep view of a single post. Contains, roughly in order of current prominence:

- **Pipeline status rail** — the 6 stages as a vertical stepper with pending/active/done/failed states
- **Title, slug, tags**
- **Status banner** — contextual: running / needs review / scheduled with countdown / failed with error / stuck
- **Action buttons** — approve, reject with feedback, publish now, re-run, delete
- **Live job logs** — a black terminal-style pane, streaming, ~500 lines
- **Research digest** — structured JSON: sources, confidence score, target keyword, the India-first angle
- **Audit verdict** — a score, a pass/fail recommendation, reasoning
- **The draft itself** — 1,400–2,000 words of MDX
- **Social kit** — LinkedIn carousel, 5 post variants, X threads, single tweets, hashtags. Each is a copy-to-clipboard block.
- **Schema JSON-LD** — Article + FAQ structured data

That is a **lot** of content on one page, and it's currently a single long undifferentiated
scroll. The reader has three completely different intents here — *monitor* (is it progressing?),
*judge* (is this any good?), and *harvest* (give me the social copy to paste). Those probably
shouldn't all be the same column. Tabs, panes, progressive disclosure — designer's call, but the
current "everything stacked forever" is the thing to fix.

Note the social kit is genuinely a different mode of use: the user is copy-pasting into LinkedIn
and X, one block at a time. Copy affordances should be excellent.

### 6.3 Analytics (`/stats`)

Read-only. All of this data is live and available:

**Totals** — topics, published, scheduled, queued, needsReview, failed, inProgress

**Content quality** — post count, total words, avg + median word count, % with hero image,
% with schema, % with social kit, avg audit score, avg research confidence

**Cadence** — posts published per day for the last 30 days (zero-filled, so it charts cleanly),
last published timestamp, next scheduled publish, full upcoming schedule list

**Views** — total, last 7 days, last 30 days, unique posts viewed, views per day for 30 days,
top 10 posts by views

**Tags** — top 12 tags with counts

The cadence chart is arguably the most important single visual in the entire product: it shows
at a glance whether the engine is actually running on rhythm or has gone erratic. A 30-day bar
chart with visible gaps tells the health story faster than any number.

Views may legitimately be **zero** — the tracking snippet isn't on the live site yet. Design the
zero state so it reads as "not wired up yet", not "you have no readers".

## 7. Constraints

- **Next.js App Router**, React, TypeScript. Client components, `fetch` to JSON API routes.
- Currently **plain CSS with CSS custom properties** (`--text-muted`, `--red`, etc.) and utility
  classes (`card`, `btn`, `btn-primary`, `btn-sm`, `btn-outline`, `pipeline-step`, `digest-section`,
  `spinner`, `empty`). A design system replacing this is welcome — say so explicitly if you go there.
- **Polls constantly** — the grid refreshes every 3–10s, detail view every 4s. Anything that
  animates or transitions must survive a re-render every few seconds without flickering, jumping,
  or restarting. This is a real constraint, not a footnote.
- **Mobile matters.** The veto decision genuinely happens on a phone.
- Dark/light: currently light. Pick deliberately and commit; if both, both must feel intentional.

## 8. What not to do

- Don't build a generic SaaS admin template — sidebar, uniform stat cards, three-column grid, done.
- Don't give all eight statuses equal visual weight. Two of them matter.
- Don't make `queued` look like a problem. It is the normal resting state and there will be dozens.
- Don't bury the veto countdown.
- Don't decorate. This is an instrument. Every non-functional pixel is noise a busy person has to
  filter to find out whether their content engine is on fire.

## 9. The one-sentence test

> Open it on a phone, and within three seconds know whether the engine is healthy and whether
> anything is about to publish that shouldn't.

If a design choice doesn't serve that, it's decoration.
