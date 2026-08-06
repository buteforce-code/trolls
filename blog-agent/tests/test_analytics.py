"""Analytics ingestion tests.

Two classes of bug are worth pinning here, because both produce *plausible*
numbers rather than crashes — the kind that get believed and acted on:

  1. Averaging `position` without weighting by impressions. Search Console
     reports position as a per-impression average, so folding two URLs into one
     slug with a plain mean invents a rank the site never held. It always errs
     optimistic, which is the worst direction for a system that decides what to
     write next based on which posts are doing well.

  2. Mis-attributing a URL to the wrong slug. GSC and GA4 disagree on trailing
     slashes, host, protocol and percent-encoding, so the same page arrives in
     several shapes and each one must land on the same post.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm.analytics.ingest import _fold_ga4, _fold_search  # noqa: E402
from swarm.analytics.slugmap import normalise_path, resolve, slug_from_path  # noqa: E402


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


# ── slug mapping ──────────────────────────────────────────────────────────────
def test_normalise_path_variants() -> int:
    """Every shape these APIs emit for one page must reduce to one path."""
    failures = 0
    cases = {
        "https://www.buteforce.com/blog/sarvam-code": "/blog/sarvam-code",
        "https://buteforce.com/blog/sarvam-code/": "/blog/sarvam-code",
        "http://www.buteforce.com/blog/sarvam-code?utm_source=li": "/blog/sarvam-code",
        "https://www.buteforce.com/blog/sarvam-code#intro": "/blog/sarvam-code",
        "/blog/sarvam-code": "/blog/sarvam-code",
        "/blog/sarvam-code/": "/blog/sarvam-code",
        "/blog/SARVAM-code": "/blog/sarvam-code",
        "https://www.buteforce.com/": "/",
        "": "",
    }
    for raw, expected in cases.items():
        got = normalise_path(raw)
        if got != expected:
            _fail(f"normalise_path({raw!r}) -> {got!r}, expected {expected!r}")
            failures += 1
    return failures


def test_slug_from_path_rejects_non_posts() -> int:
    """Only real post paths yield a slug — never the homepage or a section page."""
    failures = 0
    for path in ("/", "/services", "/blog", "/blog/", "/about/team", "/blog/a/b"):
        if slug_from_path(path) is not None:
            _fail(f"slug_from_path({path!r}) should be None, got {slug_from_path(path)!r}")
            failures += 1
    if slug_from_path("/blog/computer-vision-for-fmcg") != "computer-vision-for-fmcg":
        _fail("valid post path did not resolve")
        failures += 1
    return failures


def test_resolve_prefers_index_then_pattern() -> int:
    failures = 0
    index = {"/blog/legacy-url": "renamed-slug"}

    if resolve("https://www.buteforce.com/blog/legacy-url/", index) != "renamed-slug":
        _fail("indexed published_url did not win")
        failures += 1
    # Not in the index, but structurally a post — the pattern fallback covers it.
    if resolve("https://www.buteforce.com/blog/brand-new-post", index) != "brand-new-post":
        _fail("pattern fallback did not resolve an unindexed post")
        failures += 1
    if resolve("https://www.buteforce.com/services", index) is not None:
        _fail("a non-post page resolved to a slug")
        failures += 1
    return failures


# ── folding ───────────────────────────────────────────────────────────────────
def test_position_is_impression_weighted() -> int:
    """The bug this file exists for.

    One page at position 30 with 1 impression, another at position 5 with 99.
    Impression-weighted this is ~5.25 — barely moved. A plain mean would report
    17.5, inventing a page-2 problem on a page that is actually doing fine.
    """
    failures = 0
    rows = [
        {"date": "2026-08-01", "page": "/blog/x", "impressions": 1, "clicks": 0, "position": 30.0},
        {"date": "2026-08-01", "page": "/blog/x", "impressions": 99, "clicks": 5, "position": 5.0},
    ]
    folded = _fold_search(rows, lambda r: (r["date"], "x"))
    slot = folded[("2026-08-01", "x")]

    if slot["impressions"] != 100 or slot["clicks"] != 5:
        _fail(f"counts should sum: got {slot['impressions']} impressions, {slot['clicks']} clicks")
        failures += 1
    if slot["position"] != 5.25:
        _fail(f"expected weighted position 5.25, got {slot['position']} (plain mean would be 17.5)")
        failures += 1
    if slot["ctr"] != 0.05:
        _fail(f"ctr should be recomputed from totals, got {slot['ctr']}")
        failures += 1
    return failures


def test_zero_impressions_has_no_position() -> int:
    """Position with no impressions is undefined. Storing 0.0 would read as rank 1."""
    failures = 0
    rows = [{"date": "2026-08-01", "page": "/blog/x", "impressions": 0, "clicks": 0, "position": 0.0}]
    slot = _fold_search(rows, lambda r: (r["date"], "x"))[("2026-08-01", "x")]
    if slot["position"] is not None:
        _fail(f"expected None for zero-impression position, got {slot['position']}")
        failures += 1
    return failures


def test_fold_skips_unresolvable_rows() -> int:
    """Rows that map to no post are dropped, not attributed to a neighbour."""
    failures = 0
    rows = [
        {"date": "2026-08-01", "page": "/services", "impressions": 50, "clicks": 3, "position": 4.0},
        {"date": "2026-08-01", "page": "/blog/x", "impressions": 10, "clicks": 1, "position": 8.0},
    ]
    folded = _fold_search(rows, lambda r: (r["date"], "x") if r["page"] == "/blog/x" else None)
    if len(folded) != 1:
        _fail(f"expected 1 folded key, got {len(folded)}")
        failures += 1
    if folded[("2026-08-01", "x")]["impressions"] != 10:
        _fail("unresolvable row leaked into a post's totals")
        failures += 1
    return failures


def test_ga4_engagement_rate_weighted_by_views() -> int:
    """Averaging two ratios is wrong when the paths behind them differ in size."""
    failures = 0
    rows = [
        {"date": "2026-08-01", "path": "/blog/x", "views": 90, "users": 80,
         "engaged_seconds": 900.0, "engagement_rate": 0.9},
        {"date": "2026-08-01", "path": "/blog/x/", "views": 10, "users": 9,
         "engaged_seconds": 20.0, "engagement_rate": 0.1},
    ]
    slot = _fold_ga4(rows, lambda p: "x")[("2026-08-01", "x")]

    if slot["views"] != 100 or slot["users"] != 89:
        _fail(f"counts should sum: {slot['views']} views, {slot['users']} users")
        failures += 1
    if slot["engaged_seconds"] != 920.0:
        _fail(f"engagement seconds should sum, got {slot['engaged_seconds']}")
        failures += 1
    if slot["engagement_rate"] != 0.82:
        _fail(f"expected view-weighted 0.82, got {slot['engagement_rate']} (plain mean = 0.5)")
        failures += 1
    return failures


def main() -> int:
    tests = [
        ("URL variants normalise to one path", test_normalise_path_variants),
        ("non-post paths yield no slug", test_slug_from_path_rejects_non_posts),
        ("resolve prefers published_url, falls back to pattern", test_resolve_prefers_index_then_pattern),
        ("position is impression-weighted", test_position_is_impression_weighted),
        ("zero impressions has no position", test_zero_impressions_has_no_position),
        ("unresolvable rows are dropped", test_fold_skips_unresolvable_rows),
        ("GA4 engagement rate is view-weighted", test_ga4_engagement_rate_weighted_by_views),
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
