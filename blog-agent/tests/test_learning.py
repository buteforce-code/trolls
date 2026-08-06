"""Learning layer tests.

These pin the properties that make the layer safe to act on. Each one guards
against a specific way a content-scoring system goes wrong quietly:

  * One viral post capturing the whole engine. The Sarvam post is ~60% of all
    search visibility. Without log damping and shrinkage, the learner concludes
    "always write about AI coding tools" from a single observation.

  * Judging posts before they can rank. SEO ramps over weeks. Score a 3-day-old
    post next to a 60-day-old one and you measure age, then teach the engine
    that whatever it just published was a mistake.

  * Confident claims from thin evidence. An arm with one success must not report
    100%. The uncertainty is the useful part.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm.learning import bandit, config  # noqa: E402
from swarm.learning.scorer import PostScore, _position_quality, cluster_for, score_one  # noqa: E402


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


def _post(slug: str, cluster: str, platform: str, success: bool,
          age: int = 60, matured: bool = True) -> PostScore:
    return PostScore(
        slug=slug, cluster=cluster, source_kind="ideator", source_platform=platform,
        age_days=age, matured=matured,
        impressions=100 if success else 0, clicks=1 if success else 0,
        success=success,
    )


# ── scorer ────────────────────────────────────────────────────────────────────
def test_immature_posts_are_not_judged() -> int:
    """A post younger than MIN_AGE_DAYS is carried but flagged unmatured."""
    failures = 0
    young = score_one("x", "dev-tools", "ideator", "linkedin",
                      age_days=config.MIN_AGE_DAYS - 1,
                      impressions=0, clicks=0, position=None, views=0, engagement_rate=None)
    old = score_one("y", "dev-tools", "ideator", "linkedin",
                    age_days=config.MIN_AGE_DAYS,
                    impressions=0, clicks=0, position=None, views=0, engagement_rate=None)
    if young.matured:
        _fail("a post below the age floor was marked matured")
        failures += 1
    if not old.matured:
        _fail("a post at the age floor was not marked matured")
        failures += 1
    return failures


def test_log_damping_stops_one_outlier_dominating() -> int:
    """353 impressions must beat 3 clearly — but not by 100x.

    This is the Sarvam-post guard. A linear term would make one newsjack worth
    more than every other post combined, and the engine would chase it forever.
    """
    failures = 0
    big = score_one("big", "dev-tools", "ideator", "linkedin", age_days=60,
                    impressions=353, clicks=0, position=None, views=0, engagement_rate=None)
    small = score_one("small", "dev-tools", "ideator", "linkedin", age_days=60,
                      impressions=3, clicks=0, position=None, views=0, engagement_rate=None)

    if big.outcome_score <= small.outcome_score:
        _fail("the higher-impression post did not score higher")
        failures += 1
    ratio = big.outcome_score / max(small.outcome_score, 1e-9)
    if ratio > 10:
        _fail(f"outlier dominates: score ratio {ratio:.1f}x for a 118x impression gap")
        failures += 1
    return failures


def test_position_quality_bounds() -> int:
    failures = 0
    cases = [(1.0, 1.0), (config.POSITION_FLOOR, 0.0), (config.POSITION_FLOOR + 50, 0.0), (None, 0.0)]
    for position, expected in cases:
        got = _position_quality(position)
        if abs(got - expected) > 1e-9:
            _fail(f"_position_quality({position}) = {got}, expected {expected}")
            failures += 1
    # Page 2 must be worth strictly less than page 1 but more than nothing.
    p5, p15 = _position_quality(5), _position_quality(15)
    if not (0 < p15 < p5 < 1.0):
        _fail(f"expected 0 < pos15 ({p15}) < pos5 ({p5}) < 1")
        failures += 1
    return failures


def test_success_needs_a_real_outcome() -> int:
    failures = 0
    nothing = score_one("a", "c", "k", "p", 60, 0, 0, None, 0, None)
    clicked = score_one("b", "c", "k", "p", 60, 5, config.SUCCESS_CLICKS, None, 0, None)
    seen = score_one("c", "c", "k", "p", 60, config.SUCCESS_IMPRESSIONS, 0, None, 0, None)
    if nothing.success:
        _fail("a post with no impressions and no clicks counted as a success")
        failures += 1
    if not clicked.success:
        _fail("a post that earned a click did not count as a success")
        failures += 1
    if not seen.success:
        _fail("a post at the impression threshold did not count as a success")
        failures += 1
    return failures


def test_cluster_mapping_is_stable() -> int:
    failures = 0
    cases = {
        ("computer-vision", "fmcg"): "manufacturing-cv",
        ("retail", "footfall"): "retail-cv",
        ("ocr",): "document-ai",
        ("ai-agents",): "ai-agents",
        ("unmapped-tag",): "other",
    }
    for tags, expected in cases.items():
        got = cluster_for(list(tags))
        if got != expected:
            _fail(f"cluster_for({tags}) = {got!r}, expected {expected!r}")
            failures += 1
    # Falls back to the title when tags say nothing useful.
    if cluster_for([], "Sarvam Code: the Claude Code rival") != "dev-tools":
        _fail("title fallback did not classify a dev-tools post")
        failures += 1
    return failures


# ── bandit ────────────────────────────────────────────────────────────────────
def test_single_observation_arm_stays_uncertain() -> int:
    """One success must not produce a 100% belief.

    This is what stops the engine from betting everything on the first thing
    that happens to work.
    """
    failures = 0
    scores = [_post("a", "dev-tools", "linkedin", success=True)]
    scores += [_post(f"f{i}", "manufacturing-cv", "own_analysis", success=False) for i in range(8)]

    arms = {a.arm: a for a in bandit.fit(scores, seed=1)}
    lucky = arms["dev-tools:linkedin"]

    if lucky.mean > 0.9:
        _fail(f"one observation produced a {lucky.mean:.0%} belief — no shrinkage applied")
        failures += 1
    if lucky.uncertainty < 0.2:
        _fail(f"one observation produced a narrow interval ({lucky.uncertainty:.2f} wide)")
        failures += 1
    if not (lucky.ci_low <= lucky.mean <= lucky.ci_high):
        _fail("posterior mean falls outside its own credible interval")
        failures += 1
    return failures


def test_more_evidence_narrows_the_interval() -> int:
    """The interval must shrink as observations accumulate — otherwise the
    engine never becomes confident about anything and never exploits."""
    failures = 0
    thin = bandit.fit([_post("a", "c1", "linkedin", True)], seed=2)
    thick = bandit.fit([_post(f"a{i}", "c1", "linkedin", True) for i in range(30)], seed=2)

    thin_arm = next(a for a in thin if a.arm == "c1:linkedin")
    thick_arm = next(a for a in thick if a.arm == "c1:linkedin")

    if thick_arm.uncertainty >= thin_arm.uncertainty:
        _fail(f"30 observations ({thick_arm.uncertainty:.3f}) were not more certain "
              f"than 1 ({thin_arm.uncertainty:.3f})")
        failures += 1
    if thick_arm.mean <= thin_arm.mean:
        _fail("sustained success did not raise the posterior mean")
        failures += 1
    return failures


def test_old_observations_count_less() -> int:
    """Time decay: a win from two half-lives ago is weaker evidence than a fresh one."""
    failures = 0
    fresh = bandit.fit([_post("a", "c1", "linkedin", True, age=1)], seed=3)
    stale = bandit.fit(
        [_post("a", "c1", "linkedin", True, age=int(config.DECAY_HALF_LIFE_DAYS * 2))], seed=3)

    fresh_arm = next(a for a in fresh if a.arm == "c1:linkedin")
    stale_arm = next(a for a in stale if a.arm == "c1:linkedin")

    if stale_arm.trials >= fresh_arm.trials:
        _fail(f"a two-half-life-old observation weighed {stale_arm.trials} vs "
              f"{fresh_arm.trials} for a fresh one")
        failures += 1
    if stale_arm.mean >= fresh_arm.mean:
        _fail("a stale success moved the posterior as much as a fresh one")
        failures += 1
    return failures


def test_unseen_arms_still_get_explored() -> int:
    """A topic from an arm with no history must be rankable, not ranked last by
    default — that is how the engine finds anything new."""
    failures = 0
    scores = [_post(f"a{i}", "manufacturing-cv", "own_analysis", True) for i in range(10)]
    arms = bandit.fit(scores, seed=4)
    rate = bandit.global_success_rate(scores)

    candidates = [
        {"slug": "known", "arm": "manufacturing-cv:own_analysis"},
        {"slug": "novel", "arm": "dev-tools:linkedin"},
    ]
    ranked = bandit.rank_candidates(candidates, arms, rate, seed=4)

    if len(ranked) != 2:
        _fail(f"expected 2 ranked candidates, got {len(ranked)}")
        failures += 1
    novel = next(r for r in ranked if r["slug"] == "novel")
    if novel["arm_trials"] != 0:
        _fail("an unseen arm reported prior observations")
        failures += 1
    if not (0.0 <= novel["sampled"] <= 1.0):
        _fail(f"Thompson draw out of range: {novel['sampled']}")
        failures += 1
    if not novel["explanation"].get("reason"):
        _fail("a decision carried no human-readable reason")
        failures += 1
    return failures


def test_density_curve_is_plottable() -> int:
    """The chart depends on this, and a NaN in the curve renders as a blank panel."""
    failures = 0
    arms = bandit.fit([_post(f"a{i}", "c1", "linkedin", i % 2 == 0) for i in range(6)], seed=5)
    arm = arms[0]
    if len(arm.density) < 10:
        _fail(f"density curve too coarse to plot: {len(arm.density)} points")
        failures += 1
    if any(p["y"] < 0 or p["y"] != p["y"] for p in arm.density):
        _fail("density curve contains a negative or NaN value")
        failures += 1
    if max(p["y"] for p in arm.density) <= 0:
        _fail("density curve is flat at zero")
        failures += 1
    return failures


def test_calibration_reports_brier() -> int:
    failures = 0
    scores = [_post(f"a{i}", "c1", "linkedin", True) for i in range(5)]
    scores += [_post(f"b{i}", "c2", "reddit", False) for i in range(5)]
    arms = bandit.fit(scores, seed=6)
    cal = bandit.calibration(scores, arms)

    if cal["n"] != 10:
        _fail(f"calibration saw {cal['n']} posts, expected 10")
        failures += 1
    if cal["brier"] is None or not (0.0 <= cal["brier"] <= 1.0):
        _fail(f"Brier score out of range: {cal['brier']}")
        failures += 1
    return failures


def test_immature_posts_never_reach_the_bandit() -> int:
    """A post too young to judge must not update any arm."""
    failures = 0
    scores = [_post("young", "c1", "linkedin", False, age=1, matured=False)]
    if bandit.fit(scores, seed=7):
        _fail("an immature post created an arm")
        failures += 1
    return failures


# ── format classification ─────────────────────────────────────────────────────
def test_format_classification() -> int:
    """Structural, not semantic — so it is reproducible and free.

    Order matters in the classifier: a case study usually also contains a
    numbered list, and a comparison usually also reads like a guide, so the most
    distinctive test has to win.
    """
    from swarm.learning.formats import classify

    failures = 0
    cases = {
        ("3 Real Computer Vision Case Studies From Indian Manufacturing", ""): "listicle",
        ("AI Automation Company vs. AI Platform: Which Is Right for Your Factory?", ""): "comparison",
        ("Build vs Buy: Should You Build an AI Quality Control System?", ""): "comparison",
        ("How We Deployed Computer Vision on an Orthopedic Line (Full Case Study)", ""): "case_study",
        ("Computer Vision Quality Control: The Complete 2026 Guide", ""): "guide",
        ("Sarvam Code: the Claude Code and Codex Rival", ""): "news",
    }
    for (title, body), expected in cases.items():
        got = classify(title, body)
        if got != expected:
            _fail(f"classify({title[:44]!r}) = {got!r}, expected {expected!r}")
            failures += 1
    return failures


def test_format_falls_back_on_structure() -> int:
    """With no title cue, the shape of the draft decides."""
    from swarm.learning.formats import classify

    failures = 0
    numbered = "## 1. First thing\ntext\n## 2. Second thing\ntext\n## 3. Third\ntext\n"
    if classify("Some Neutral Title", numbered) != "listicle":
        _fail("majority-numbered headings did not classify as a listicle")
        failures += 1

    questions = "## What is it?\na\n## Why does it matter?\nb\n## How much?\nc\n"
    if classify("Some Neutral Title", questions) != "explainer":
        _fail("majority-question headings did not classify as an explainer")
        failures += 1
    return failures


def test_format_arms_are_off_by_default() -> int:
    """Splitting arms by format at this sample size would make every cell
    degenerate. The switch must default off."""
    from swarm.learning.formats import FORMAT_ARMS

    failures = 0
    if FORMAT_ARMS:
        _fail("LEARN_FORMAT_ARMS defaults on — arms would be too sparse to learn from")
        failures += 1

    post = _post("a", "dev-tools", "linkedin", True)
    post.content_format = "listicle"
    if ":listicle" in post.arm:
        _fail(f"format leaked into the arm key while disabled: {post.arm}")
        failures += 1
    return failures


def main() -> int:
    tests = [
        ("immature posts are not judged", test_immature_posts_are_not_judged),
        ("log damping stops one outlier dominating", test_log_damping_stops_one_outlier_dominating),
        ("position quality is bounded and ordered", test_position_quality_bounds),
        ("success needs a real outcome", test_success_needs_a_real_outcome),
        ("cluster mapping is stable", test_cluster_mapping_is_stable),
        ("a single observation stays uncertain", test_single_observation_arm_stays_uncertain),
        ("more evidence narrows the interval", test_more_evidence_narrows_the_interval),
        ("old observations count less", test_old_observations_count_less),
        ("unseen arms still get explored", test_unseen_arms_still_get_explored),
        ("density curve is plottable", test_density_curve_is_plottable),
        ("calibration reports a Brier score", test_calibration_reports_brier),
        ("immature posts never reach the bandit", test_immature_posts_never_reach_the_bandit),
        ("format classification from title cues", test_format_classification),
        ("format falls back on draft structure", test_format_falls_back_on_structure),
        ("format arms are off by default", test_format_arms_are_off_by_default),
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
