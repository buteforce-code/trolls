"""Distribution policy tests.

Two failures would make this feature unusable, and both are silent, so both are pinned here:

  * double-posting — the same variant sent twice to a real person's professional profile;
  * dumping — a month of queued content emptied into one afternoon because the cron fires
    hourly and nothing throttled it.

Everything else is recoverable. `swarm/distribute` is import-clean, so these run with no
network and no database.

    python tests/test_distribute.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm import distribute  # noqa: E402
from swarm.distribute import LINKEDIN, QUEUED, SENT, SKIPPED, X, Send  # noqa: E402

PUB = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)

KIT = {
    "linkedin": {
        "founder_story": "We shipped a vision system that holds 99.2% at 120 items/min.",
        "data_post": "Three numbers from ten production deployments.",
        "contrarian": "Most QC pilots fail for a reason nobody writes about.",
        "company_page": "New on the Buteforce blog.",
        "carousel": [{"text": "Slide one"}, {"text": "Slide two"}],
    },
    "x": {
        "thread_numbered": ["1/ A vision line runs at 120 items/min.", "2/ Here is how."],
        "tweets": ["One-off tweet."],
    },
    "hashtags": {"linkedin": "#ComputerVision #Manufacturing", "x": "#CV"},
    "first_comment_link": "Full breakdown on the blog.",
}


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


# ── the two failures that matter ──────────────────────────────────────────────────────────
def test_the_natural_key_prevents_double_posting() -> int:
    """Enqueueing is idempotent on (slug, channel, variant) — the DB enforces it too."""
    f = 0
    first = distribute.plan_for("a-post", KIT, PUB, url="https://x.test/blog/a-post")
    again = distribute.plan_for("a-post", KIT, PUB, url="https://x.test/blog/a-post")
    keys = {s.key for s in first}
    if len(keys) != len(first):
        _fail("plan_for produced two sends with the same natural key")
        f += 1
    if {s.key for s in again} != keys:
        _fail("re-planning the same post produced different keys — enqueue is not idempotent")
        f += 1
    return f


def test_one_kit_is_not_six_simultaneous_posts() -> int:
    """The whole reason this module exists rather than a loop over social_json."""
    f = 0
    sends = [s for s in distribute.plan_for("a-post", KIT, PUB) if s.status == QUEUED]
    times = sorted({s.due_at for s in sends})
    if len(times) < 4:
        _fail(f"the kit was scheduled into only {len(times)} distinct slots")
        f += 1
    if (times[-1] - times[0]) < timedelta(days=7):
        _fail(f"the whole kit lands inside {times[-1] - times[0]} — that reads as a bot")
        f += 1
    if sends[0].channel != LINKEDIN or sends[0].variant != "founder_story":
        _fail(f"the chain should open with the founder story, got {sends[0].variant!r}")
        f += 1
    return f


def test_cadence_gap_blocks_a_second_send() -> int:
    f = 0
    now = PUB + timedelta(days=30)
    sends = distribute.plan_for("a-post", KIT, PUB, now=now)
    due = [s for s in sends if s.status == QUEUED]

    fresh = distribute.next_due(due, gap_hours=24, last_sent_at=now - timedelta(hours=1), now=now)
    if fresh is not None:
        _fail("a send went out one hour after the last one, against a 24h gap")
        f += 1
    later = distribute.next_due(due, gap_hours=24, last_sent_at=now - timedelta(hours=25), now=now)
    if later is None:
        _fail("nothing sent 25 hours after the last one, against a 24h gap")
        f += 1
    never = distribute.next_due(due, gap_hours=24, last_sent_at=None, now=now)
    if never is None:
        _fail("the first ever send was blocked by a gap with nothing to measure from")
        f += 1
    return f


def test_only_one_send_per_tick() -> int:
    f = 0
    now = PUB + timedelta(days=30)
    due = [s for s in distribute.plan_for("a-post", KIT, PUB, now=now) if s.status == QUEUED]
    picked = distribute.next_due(due, gap_hours=24, last_sent_at=None, now=now)
    if not isinstance(picked, Send):
        _fail("next_due must return exactly one send, not a batch")
        f += 1
    return f


# ── backlog and ordering ──────────────────────────────────────────────────────────────────
def test_a_backlog_is_sent_oldest_first_not_dropped() -> int:
    """A post published during a week of downtime is late, not forfeited."""
    f = 0
    now = PUB + timedelta(days=40)
    due = [s for s in distribute.plan_for("old-post", KIT, PUB, now=now) if s.status == QUEUED]
    if not due:
        _fail("an overdue post produced nothing to send")
        return f + 1
    picked = distribute.next_due(due, gap_hours=24, last_sent_at=None, now=now)
    if picked.variant != "founder_story":
        _fail(f"the backlog drained out of order, started with {picked.variant!r}")
        f += 1
    return f


def test_future_slots_are_not_due_yet() -> int:
    f = 0
    now = PUB + timedelta(hours=1)
    due = [s for s in distribute.plan_for("a-post", KIT, PUB, now=now) if s.status == QUEUED]
    picked = distribute.next_due(due, gap_hours=24, last_sent_at=None, now=now)
    if picked is None:
        _fail("the day-0 send was not due one hour after publication")
        f += 1
    elif picked.variant != "founder_story":
        _fail(f"a future-dated variant was sent early: {picked.variant!r}")
        f += 1
    return f


# ── composing ─────────────────────────────────────────────────────────────────────────────
def test_composed_post_carries_body_link_and_hashtags() -> int:
    f = 0
    text = distribute.compose(KIT, LINKEDIN, "founder_story", url="https://x.test/blog/a-post")
    for fragment in ("99.2%", "https://x.test/blog/a-post", "#ComputerVision"):
        if fragment not in text:
            _fail(f"composed post is missing {fragment!r}")
            f += 1
    return f


def test_an_x_thread_list_becomes_text() -> int:
    f = 0
    text = distribute.compose(KIT, X, "thread_numbered")
    if "1/" not in text or "2/" not in text:
        _fail(f"a list-shaped thread did not flatten into text: {text!r}")
        f += 1
    return f


def test_a_dict_is_never_posted_as_a_repr() -> int:
    """Posting `{'text': ...}` to a company page is the kind of error that is funny once."""
    f = 0
    kit = {"linkedin": {"founder_story": {"unexpected": "shape"}}}
    text = distribute.compose(kit, LINKEDIN, "founder_story")
    if "{" in text or "'" in text:
        _fail(f"an unrecognised shape leaked a Python repr: {text!r}")
        f += 1
    return f


def test_missing_variants_are_skipped_not_dropped() -> int:
    """A kit missing a variant is a prompt problem; a sender that never tried is an outage.
    They must not look the same."""
    f = 0
    thin = {"linkedin": {"founder_story": "Only this one."}, "hashtags": {}}
    sends = distribute.plan_for("a-post", thin, PUB)
    if len(sends) != len(distribute.DEFAULT_PLAN):
        _fail(f"expected one send per planned slot, got {len(sends)}")
        f += 1
    skipped = [s for s in sends if s.status == SKIPPED]
    if len(skipped) != len(distribute.DEFAULT_PLAN) - 1:
        _fail(f"missing variants were dropped rather than recorded: {len(skipped)} skipped")
        f += 1
    return f


def test_over_length_posts_are_skipped_not_truncated() -> int:
    f = 0
    kit = {"x": {"thread_numbered": "x" * 400}, "linkedin": {}, "hashtags": {}}
    sends = distribute.plan_for("a-post", kit, PUB)
    x_send = next(s for s in sends if s.channel == X)
    if x_send.status != SKIPPED:
        _fail(f"a 400-char single tweet was queued rather than skipped ({x_send.status})")
        f += 1
    if not distribute.too_long("x" * 400, X):
        _fail("the X length limit is not being enforced")
        f += 1
    if distribute.too_long("x" * 400, LINKEDIN):
        _fail("LinkedIn's 3000-char limit is being applied as if it were X's")
        f += 1
    return f


def test_a_thread_is_measured_per_tweet_not_as_one_blob() -> int:
    """The live-data bug: all 33 X threads were skipped as over-length.

    A numbered thread had been flattened to one string and measured against the 280-char
    single-tweet limit, so every thread the social agent ever wrote was discarded before it
    could be posted. A thread is not a long tweet.
    """
    f = 0
    thread = [f"{i}/ " + "word " * 40 for i in range(1, 5)]   # ~215 chars each, ~880 joined
    kit = {"x": {"thread_numbered": thread}, "linkedin": {}, "hashtags": {}}

    joined = distribute.compose(kit, X, "thread_numbered")
    if len(joined) <= 280:
        _fail("fixture problem: the joined thread should exceed one tweet")
        f += 1
    sends = distribute.plan_for("a-post", kit, PUB)
    x_send = next(s for s in sends if s.channel == X)
    if x_send.status == SKIPPED:
        _fail("a valid multi-tweet thread was skipped as over-length")
        f += 1

    # But an individual tweet that is genuinely too long still fails.
    long_thread = ["1/ ok", "2/ " + "x" * 400]
    kit2 = {"x": {"thread_numbered": long_thread}, "linkedin": {}, "hashtags": {}}
    over = next(s for s in distribute.plan_for("b-post", kit2, PUB) if s.channel == X)
    if over.status != SKIPPED:
        _fail("a thread containing a 400-char tweet was queued")
        f += 1
    return f


def test_backlog_slots_keep_their_real_dates() -> int:
    """Clamping overdue slots to `now` collapsed a 132-send backlog onto one timestamp and
    destroyed the ordering that decides what goes out first."""
    f = 0
    now = PUB + timedelta(days=90)
    sends = [s for s in distribute.plan_for("old", KIT, PUB, now=now) if s.status == QUEUED]
    dues = {s.due_at for s in sends}
    if len(dues) < 3:
        _fail(f"overdue sends collapsed onto {len(dues)} timestamp(s)")
        f += 1
    if any(s.due_at >= now for s in sends):
        _fail("an overdue send was pushed forward to now instead of keeping its date")
        f += 1
    return f


# ── kit loading ───────────────────────────────────────────────────────────────────────────
def test_social_json_is_read_as_string_or_dict() -> int:
    """It is stored as a JSON *string* on the live table, not jsonb."""
    f = 0
    import json

    if distribute.load_kit(json.dumps(KIT)) != KIT:
        _fail("a JSON-string social_json did not parse")
        f += 1
    if distribute.load_kit(KIT) != KIT:
        _fail("a dict social_json was not passed through")
        f += 1
    for junk in (None, "", "not json", 42, []):
        if distribute.load_kit(junk) != {}:
            _fail(f"{junk!r} should load as an empty kit")
            f += 1
    return f


def test_dry_run_is_the_default() -> int:
    """Posting under a real person's name is the most irreversible thing in this repo."""
    f = 0
    import os

    saved = {k: os.environ.pop(k, None) for k in ("DISTRIBUTE_DRY_RUN", "DISTRIBUTE_PROVIDER")}
    try:
        pol = distribute.policy()
        if not pol.dry_run:
            _fail("distribution defaults to live posting — it must default to dry run")
            f += 1
        if pol.provider != "manual":
            _fail(f"default provider should be manual, got {pol.provider!r}")
            f += 1
        os.environ["DISTRIBUTE_PROVIDER"] = "none"
        if distribute.policy().enabled:
            _fail("DISTRIBUTE_PROVIDER=none did not disable distribution")
            f += 1
    finally:
        os.environ.pop("DISTRIBUTE_PROVIDER", None)
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
    return f


def main() -> int:
    tests = [
        ("natural key prevents double-posting", test_the_natural_key_prevents_double_posting),
        ("one kit is not six simultaneous posts", test_one_kit_is_not_six_simultaneous_posts),
        ("cadence gap blocks a second send", test_cadence_gap_blocks_a_second_send),
        ("only one send per tick", test_only_one_send_per_tick),
        ("backlog sent oldest first", test_a_backlog_is_sent_oldest_first_not_dropped),
        ("future slots not due yet", test_future_slots_are_not_due_yet),
        ("composed post carries link + tags", test_composed_post_carries_body_link_and_hashtags),
        ("X thread list becomes text", test_an_x_thread_list_becomes_text),
        ("no Python repr is ever posted", test_a_dict_is_never_posted_as_a_repr),
        ("missing variants skipped not dropped", test_missing_variants_are_skipped_not_dropped),
        ("over-length skipped not truncated", test_over_length_posts_are_skipped_not_truncated),
        ("thread measured per tweet", test_a_thread_is_measured_per_tweet_not_as_one_blob),
        ("backlog keeps real dates", test_backlog_slots_keep_their_real_dates),
        ("social_json reads as string or dict", test_social_json_is_read_as_string_or_dict),
        ("dry run is the default", test_dry_run_is_the_default),
    ]
    total = 0
    for name, fn in tests:
        failures = fn()
        total += failures
        print(f"{'PASS' if failures == 0 else 'FAIL'}  {name}")
    print(f"\n{'ALL TESTS PASSED' if total == 0 else f'{total} FAILURE(S)'}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
