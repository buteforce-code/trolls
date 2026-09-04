"""Distribution — shipping the social kit the swarm has been writing and throwing away.

Why this exists
---------------
`swarm/agents/social.py` runs on every post and produces a full platform-native kit: six
LinkedIn variants, two X threads, single tweets, hashtag groups, a first-comment link. It
costs a model call each time, it is persisted to `blog_posts.social_json`, and as of
2026-09-03 there were **33 kits in the database and zero had ever been published anywhere**.
A built, paid-for acquisition channel, sitting in a jsonb column.

That matters more than it sounds. This domain is 6-12 months from search mattering: a new
site sits in a suppression window for 3-6 months regardless of quality, needs roughly DA
20-30 before low-competition terms are winnable, and 12-24 months for head terms. LinkedIn
is ~80% of B2B social leads and needs no domain authority at all. For the next two quarters
it is the only lane in this system that can produce a conversation.

What this module is, and is not
-------------------------------
It is the policy: how one post's kit becomes a schedule of individual sends, when each is
due, and which states a send can be in. Import-clean — no supabase, no requests, no ADK — so
the scheduling rules are testable without a network or a database, the same split that makes
`geo.py` and `swarm/demand` testable.

It is not the sender. `providers.py` talks to LinkedIn; `queue.py` talks to Postgres.

One kit is not one post
-----------------------
The tempting implementation is "publish the kit". That would fire six LinkedIn variants of
the same article within a minute of each other, which is not distribution — it is a person
posting the same thing six times, and it reads exactly that way. The kit is *raw material
for a campaign*, so `plan_for` spreads it over eleven days in the order the repurposing chain
was designed for: the story first, the thread while the post is still new, the data angle
once, the company page last.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

# ── states ────────────────────────────────────────────────────────────────────────────────
# `ready` and `sent` are not enough. `skipped` records that a variant was deliberately not
# sent (the kit had nothing for it), which is different from one that failed and different
# again from one still waiting — and without the distinction a half-empty kit looks like a
# broken sender forever.
QUEUED = "queued"
SENT = "sent"
FAILED = "failed"
SKIPPED = "skipped"

TERMINAL = frozenset({SENT, SKIPPED})

LINKEDIN = "linkedin"
X = "x"

# The repurposing chain from the content strategy, as a schedule rather than a pile.
# (channel, variant, day offset from publication). Order and spacing are the point: the
# founder story while the post is new, the thread the next day when the post has settled,
# the data angle mid-week, the company page at the end so the personal post leads it.
DEFAULT_PLAN: tuple[tuple[str, str, int], ...] = (
    (LINKEDIN, "founder_story", 0),
    (X, "thread_numbered", 1),
    (LINKEDIN, "data_post", 3),
    (LINKEDIN, "contrarian", 6),
    (LINKEDIN, "company_page", 10),
)

# Platform hard limits. Checked here rather than discovered at the API boundary, because a
# rejected send costs a retry and a confusing error, and truncating someone's post silently
# would be worse than refusing to send it.
MAX_CHARS = {LINKEDIN: 3000, X: 280}


@dataclass(frozen=True)
class Send:
    """One thing to post, on one channel, at one time."""

    slug: str
    channel: str
    variant: str
    body: str
    due_at: datetime
    status: str = QUEUED

    @property
    def key(self) -> tuple[str, str, str]:
        """Natural key. Enqueueing is idempotent on it, so a re-run of a tick cannot
        double-post — the failure mode that makes an autonomous poster unusable."""
        return (self.slug, self.channel, self.variant)

    def as_row(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "channel": self.channel,
            "variant": self.variant,
            "body": self.body,
            "status": self.status,
            "due_at": self.due_at.isoformat(),
        }


# ── kit parsing ───────────────────────────────────────────────────────────────────────────
def load_kit(social_json: Any) -> dict[str, Any]:
    """Normalise whatever is in `social_json` into a dict.

    Stored as a JSON *string* by the current writer, not as jsonb — checked against the live
    table on 2026-09-03. Accepting both shapes here rather than migrating the column keeps
    this working across the 33 kits already written and whatever the column becomes later.
    """
    if isinstance(social_json, dict):
        return social_json
    if isinstance(social_json, str) and social_json.strip():
        try:
            parsed = json.loads(social_json)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _flatten(value: Any) -> str:
    """Render one kit entry as the text that will actually be posted.

    An X thread arrives as a list of tweets and a LinkedIn post as a string; a carousel
    arrives as a list of slide dicts. Joining with blank lines is right for a thread and for
    slides alike, and anything unrecognised becomes empty rather than `str(dict)` — posting
    a Python repr to a company page is the kind of error that is only funny once.
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_flatten(v) for v in value]
        return "\n\n".join(p for p in parts if p)
    if isinstance(value, dict):
        for key in ("text", "body", "content", "post", "caption"):
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key].strip()
    return ""


def hashtags_for(kit: dict[str, Any], channel: str) -> str:
    tags = (kit.get("hashtags") or {})
    if not isinstance(tags, dict):
        return ""
    return _flatten(tags.get(channel))


def segments(kit: dict[str, Any], channel: str, variant: str) -> list[str]:
    """The individual posts this variant becomes. A thread is many; a post is one.

    The distinction is load-bearing for length. On the first live run all 33 X threads were
    skipped as over-length, because a numbered thread had been flattened to one string and
    then measured against the 280-character single-tweet limit. A thread is not a long tweet;
    it is several short ones, and the limit applies to each.
    """
    channel_kit = kit.get(channel)
    raw = channel_kit.get(variant) if isinstance(channel_kit, dict) else None
    if isinstance(raw, list):
        return [text for text in (_flatten(v) for v in raw) if text]
    text = _flatten(raw)
    return [text] if text else []


def compose(kit: dict[str, Any], channel: str, variant: str, url: str = "") -> str:
    """The finished text for one send: body, hashtags, and the link.

    The link is appended for LinkedIn rather than left in a first comment. The kit carries a
    `first_comment_link` because that is the reach-optimising convention, but this system
    cannot post a comment on its own post through the member API — so a convention that would
    silently drop the link entirely is worse than the small reach cost of an inline one.
    """
    body = _flatten((kit.get(channel) or {}).get(variant) if isinstance(kit.get(channel), dict) else None)
    if not body:
        return ""

    parts = [body]
    if url:
        parts.append(url)
    tags = hashtags_for(kit, channel)
    if tags:
        parts.append(tags)
    return "\n\n".join(parts).strip()


def too_long(text: str, channel: str) -> bool:
    """Is this single post over the channel's limit?"""
    limit = MAX_CHARS.get(channel)
    return bool(limit and len(text) > limit)


def oversize(parts: list[str], composed: str, channel: str) -> bool:
    """Whether this send exceeds the channel limit, measured the way it will be posted.

    Multi-part content is posted part by part, so each part is checked on its own. Single-part
    content is checked as composed, because the link and hashtags go out with it.

    An automated X sender would have to chain the parts as replies. None exists — X's write
    API is paid, and the manual provider covers threads at zero cost — so for now a human
    posts them in order.
    """
    if len(parts) > 1:
        return any(too_long(part, channel) for part in parts)
    return too_long(composed, channel)


# ── planning ──────────────────────────────────────────────────────────────────────────────
def plan_for(
    slug: str,
    kit: dict[str, Any],
    published_at: datetime,
    url: str = "",
    plan: Iterable[tuple[str, str, int]] = DEFAULT_PLAN,
    now: datetime | None = None,
) -> list[Send]:
    """Turn one post's kit into a dated schedule of sends.

    A variant the kit does not contain is emitted as `skipped`, not dropped. Dropping it
    would make "the social agent produced four of six variants" indistinguishable from "the
    sender never tried", and the first is a prompt problem while the second is an outage.

    A slot already in the past keeps its real date. Clamping it to `now` was the first
    implementation and it was wrong: it made every one of a 132-send backlog due at the same
    instant, which destroyed the ordering that decides what goes out first. `next_due` already
    treats any past date as due, so a genuine date sorts the backlog oldest-first for free.
    """
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    sends: list[Send] = []
    for channel, variant, offset in plan:
        parts = segments(kit, channel, variant)
        text = compose(kit, channel, variant, url)
        due = published_at + timedelta(days=offset)
        if not text:
            sends.append(Send(slug, channel, variant, "", due, SKIPPED))
            continue
        if oversize(parts, text, channel):
            sends.append(Send(slug, channel, variant, text, due, SKIPPED))
            continue
        sends.append(Send(slug, channel, variant, text, due))
    return sends


def next_due(sends: list[Send], gap_hours: int, last_sent_at: datetime | None,
             now: datetime | None = None) -> Send | None:
    """The single send to make on this tick, or None.

    One per tick, and only if the cadence gap has elapsed since the last one. Both halves
    matter: a queue that drains as fast as the cron fires would post a backlog in an
    afternoon, which is the exact tell of an unattended bot — the same reasoning that made
    `publish_gap_hours` independent of the veto window in `swarm/settings.py`.
    """
    now = now or datetime.now(timezone.utc)
    if last_sent_at is not None:
        if last_sent_at.tzinfo is None:
            last_sent_at = last_sent_at.replace(tzinfo=timezone.utc)
        if now - last_sent_at < timedelta(hours=gap_hours):
            return None

    due = [s for s in sends if s.status == QUEUED and s.due_at <= now]
    if not due:
        return None
    return sorted(due, key=lambda s: s.due_at)[0]


# ── policy ────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Policy:
    provider: str = "manual"
    gap_hours: int = 24
    enabled: bool = True
    dry_run: bool = True


def policy() -> Policy:
    """Resolve distribution settings from the environment.

    `DISTRIBUTE_DRY_RUN` defaults to **true**, matching `PUBLISH_DRY_RUN`. Posting to a real
    company page under a real person's name is the most irreversible thing in this repo — a
    published blog post can be deleted quietly, a bad LinkedIn post is seen before it is.
    Nothing goes out until someone deliberately turns that off.
    """
    provider = os.environ.get("DISTRIBUTE_PROVIDER", "manual").strip().lower()
    return Policy(
        provider=provider,
        gap_hours=_env_int("DISTRIBUTE_GAP_HOURS", 24),
        enabled=provider != "none",
        dry_run=os.environ.get("DISTRIBUTE_DRY_RUN", "true").strip().lower() != "false",
    )


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)).strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def summarise(sends: list[Send]) -> str:
    counts: dict[str, int] = {}
    for s in sends:
        counts[s.status] = counts.get(s.status, 0) + 1
    if not counts:
        return "[distribute] nothing queued"
    return "[distribute] " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))
