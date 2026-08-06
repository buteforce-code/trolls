"""Trend scout tests.

The relevance gate is the load-bearing part. Everything downstream — ideation,
topic selection, eventually what gets published — trusts that whatever reaches it
is something this brand can credibly write about.

The first live sweep failed that: "tucson weather" and "flight" passed, because
`"ai" in text` matches inside r-ai-nfall and -ai-r. These tests pin the fix, and
pin the shape of the failure so it cannot return quietly.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm.trends.scout import relevance_of, score_signal  # noqa: E402
from swarm.trends.sources import RawSignal  # noqa: E402


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


def _sig(title: str, summary: str = "", source: str = "google_trends",
         engagement: float = 100.0, hours_old: float = 1.0) -> RawSignal:
    return RawSignal(
        source=source, platform=source, title=title, summary=summary,
        engagement=engagement,
        published_at=datetime.now(timezone.utc) - timedelta(hours=hours_old),
    )


# ── the gate ──────────────────────────────────────────────────────────────────
def test_substring_false_positives_are_rejected() -> int:
    """The exact signals that leaked through on the first live sweep.

    Each contains 'ai' inside an unrelated word. None is about AI.
    """
    failures = 0
    cases = [
        ("tucson weather", "Strong winds, heavy rainfall, flooding and extreme heat"),
        ("flight", "Air travel disrupted across the region"),
        ("enhypen", "Reported death of a fan sparks debate over toxic fandom"),
        ("drake", "A$AP Rocky responds to Drake's new track"),
        ("aubrey plaza", "Actor offloads mansion after nearly one year on the market"),
    ]
    for title, summary in cases:
        relevance, reason = relevance_of(_sig(title, summary))
        if relevance >= 0.15:
            _fail(f"consumer noise passed the gate: {title!r} scored {relevance} ({reason})")
            failures += 1
    return failures


def test_genuine_tech_signals_pass() -> int:
    failures = 0
    cases = [
        ("Sarvam launches an AI coding agent", "open source model for developers"),
        ("Computer vision for defect detection on packaging lines", "inspection at line speed"),
        ("Show HN: OCR pipeline for invoice document AI", ""),
        ("Anthropic ships a new Claude coding agent", "developer tool for code generation"),
    ]
    for title, summary in cases:
        relevance, reason = relevance_of(_sig(title, summary))
        if relevance < 0.15:
            _fail(f"a real signal was rejected: {title!r} scored {relevance} ({reason})")
            failures += 1
    return failures


def test_bare_generic_term_is_not_enough() -> int:
    """A headline whose only tech word is 'ai' is too weak to act on — it
    describes half the internet."""
    failures = 0
    relevance, _ = relevance_of(_sig("How AI changed my morning routine", "a personal essay"))
    if relevance >= 0.15:
        _fail(f"a bare-'ai' headline passed the gate at {relevance}")
        failures += 1
    return failures


def test_first_party_search_demand_always_relevant() -> int:
    """A query already earning impressions on this site needs no vocabulary
    test — it is demand that literally arrived."""
    failures = 0
    relevance, reason = relevance_of(_sig("sarvam code", source="gsc_rising"))
    if relevance != 1.0:
        _fail(f"first-party demand scored {relevance} ({reason}), expected 1.0")
        failures += 1
    return failures


# ── scoring ───────────────────────────────────────────────────────────────────
def test_recency_dominates_for_newsjacking() -> int:
    """A story breaking now must outrank the same story two weeks old.

    The Sarvam post worked because it went out while the story was forming.
    Scoring that rewards a stale-but-popular thread over a breaking one would
    teach the engine the opposite lesson.
    """
    failures = 0
    fresh = score_signal(_sig("Sarvam AI coding agent launches", "open source model",
                              engagement=100, hours_old=2), set())
    stale = score_signal(_sig("Sarvam AI coding agent launches", "open source model",
                              engagement=100, hours_old=24 * 14), set())
    if fresh.score <= stale.score:
        _fail(f"fresh ({fresh.score}) did not outrank two-week-old ({stale.score})")
        failures += 1
    return failures


def test_already_covered_topics_are_rejected() -> int:
    """Novelty gate: don't propose what the site already published."""
    failures = 0
    existing = {"Computer Vision for FMCG Manufacturing in India: What Unilever Is Solving"}
    item = score_signal(
        _sig("Computer Vision for FMCG Manufacturing in India: What Unilever Is Solving",
             "inspection quality control"),
        existing)
    if item.status != "rejected":
        _fail(f"a duplicate of an existing post was accepted (score {item.score})")
        failures += 1
    if "overlaps" not in item.reject_reason:
        _fail(f"rejection reason did not explain the overlap: {item.reject_reason!r}")
        failures += 1
    return failures


def test_rejected_signals_carry_a_reason() -> int:
    """Rejections are stored so the gate can be debugged. A rejection with no
    reason makes 'nothing was trending' indistinguishable from 'gate too tight'."""
    failures = 0
    item = score_signal(_sig("tucson weather", "heavy rainfall"), set())
    if item.status != "rejected":
        _fail("consumer noise was not rejected")
        failures += 1
    if not item.reject_reason:
        _fail("a rejected signal carried no reason")
        failures += 1
    return failures


def test_fingerprint_is_stable_and_deduplicates() -> int:
    """The same story on the next sweep must update its row, not duplicate it —
    otherwise re-seeing one story inflates it into a bigger trend than it is."""
    failures = 0
    a = _sig("Sarvam Code: the Claude Code rival")
    b = _sig("sarvam code:  the claude code rival!")
    c = _sig("Something entirely different")
    if a.fingerprint != b.fingerprint:
        _fail("the same title in different casing produced different fingerprints")
        failures += 1
    if a.fingerprint == c.fingerprint:
        _fail("different titles collided on one fingerprint")
        failures += 1
    return failures


def main() -> int:
    tests = [
        ("substring false positives are rejected", test_substring_false_positives_are_rejected),
        ("genuine tech signals pass", test_genuine_tech_signals_pass),
        ("a bare generic term is not enough", test_bare_generic_term_is_not_enough),
        ("first-party search demand is always relevant", test_first_party_search_demand_always_relevant),
        ("recency dominates for newsjacking", test_recency_dominates_for_newsjacking),
        ("already-covered topics are rejected", test_already_covered_topics_are_rejected),
        ("rejected signals carry a reason", test_rejected_signals_carry_a_reason),
        ("fingerprints are stable and deduplicate", test_fingerprint_is_stable_and_deduplicates),
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
