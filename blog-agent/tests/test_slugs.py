"""Slug generation tests.

The live blog shipped seven URLs severed mid-word (``...mean-for-manuf``,
``...what-unileve``) because the old ``_slugify`` ended in ``slug[:60]``.
These tests pin the two rules that prevent a repeat: never cut inside a word,
and never end on a filler word.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm.slugs import MAX_SLUG_LEN, slugify  # noqa: E402

# Real roadmap titles from seed_topics.py — the ones that produced broken URLs.
ROADMAP_TITLES = [
    "Industrial AI for Chennai's Manufacturing Corridor: What's Possible in 2026",
    "Computer Vision Quality Control in Indian Manufacturing: The Complete 2026 Guide",
    "How We Deployed Computer Vision on an Orthopedic Manufacturing Line (Full Case Study)",
    "AI Automation Company vs. AI Platform: Which Is Right for Your Factory?",
    "Retail Footfall Analytics India 2026: Turn Your CCTV Into Business Intelligence",
    "The SITAC Effect: What India's New AI Corridors Mean for Manufacturing Startups",
    "n8n vs. Python for AI Workflow Automation: A Production Engineer's Honest Take",
    "What Does a Computer Vision System Actually Cost? 2026 India Market Reality",
    "Why Sandvik, ABB, and Volvo Need Local AI Partners in India (And What That Looks Like)",
    "Computer Vision for FMCG Manufacturing in India: What Unilever and ITC Are Doing",
    "Missed Sale Detection: How Retail AI Spots Revenue You're Leaving on the Floor",
]

# Words that must never be the last segment of a slug.
TRAILING_FILLER = {
    "and", "or", "the", "a", "an", "of", "for", "to", "in", "on", "with", "is",
    "what", "which", "how", "why", "does", "youre",
}


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


def test_never_exceeds_max() -> int:
    failures = 0
    for title in ROADMAP_TITLES:
        slug = slugify(title)
        if len(slug) > MAX_SLUG_LEN:
            _fail(f"{len(slug)} chars > {MAX_SLUG_LEN}: {slug}")
            failures += 1
    return failures


def test_never_cuts_mid_word() -> int:
    """Every segment of the slug must be a whole word from the source title."""
    failures = 0
    for title in ROADMAP_TITLES:
        slug = slugify(title)
        source = slugify(title, max_len=10_000)
        source_words = set(source.split("-"))
        for segment in slug.split("-"):
            if segment not in source_words:
                _fail(f"'{segment}' is not a whole word from title: {title!r} -> {slug}")
                failures += 1
    return failures


def test_no_trailing_filler() -> int:
    failures = 0
    for title in ROADMAP_TITLES:
        slug = slugify(title)
        last = slug.split("-")[-1]
        if last in TRAILING_FILLER:
            _fail(f"ends on filler '{last}': {slug}")
            failures += 1
    return failures


def test_short_titles_pass_through() -> int:
    """A title that already fits must not be mangled by filler-stripping."""
    failures = 0
    cases = {
        "Why We Choose YOLOv8 Over APIs for Manufacturing QC":
            "why-we-choose-yolov8-over-apis-for-manufacturing-qc",
        "Death of Pilot Projects": "death-of-pilot-projects",
    }
    for title, expected in cases.items():
        got = slugify(title)
        if got != expected:
            _fail(f"expected {expected!r}, got {got!r}")
            failures += 1
    return failures


def test_deterministic_and_clean() -> int:
    failures = 0
    for title in ROADMAP_TITLES:
        slug = slugify(title)
        if slug != slugify(title):
            _fail(f"not deterministic: {title!r}")
            failures += 1
        if slug.startswith("-") or slug.endswith("-") or "--" in slug:
            _fail(f"malformed separators: {slug}")
            failures += 1
        if slug != slug.lower():
            _fail(f"not lowercase: {slug}")
            failures += 1
    return failures


def main() -> int:
    tests = [
        ("never exceeds max length", test_never_exceeds_max),
        ("never cuts mid-word", test_never_cuts_mid_word),
        ("no trailing filler word", test_no_trailing_filler),
        ("short titles pass through intact", test_short_titles_pass_through),
        ("deterministic and well-formed", test_deterministic_and_clean),
    ]
    total = 0
    for name, fn in tests:
        failures = fn()
        total += failures
        print(f"{'PASS' if failures == 0 else 'FAIL'}  {name}")

    print("\n--- generated slugs ---")
    for title in ROADMAP_TITLES:
        slug = slugify(title)
        print(f"  {len(slug):>2}  {slug}")

    print(f"\n{'ALL TESTS PASSED' if total == 0 else f'{total} FAILURE(S)'}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
