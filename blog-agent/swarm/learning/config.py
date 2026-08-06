"""Tunable constants for the learning layer.

Every number the scorer and bandit depend on lives here, in one readable block,
because these are editorial judgements rather than implementation details. What
counts as a successful post is a decision about the business; it should not be
buried in a formula halfway down another module.

All are overridable by environment variable, so a weight can be changed on the
running service without a deploy — and the values actually used are written into
`learning_snapshots.config` on every run, so a score can always be reproduced.
"""
from __future__ import annotations

import os


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)).strip())
    except Exception:
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)).strip())
    except Exception:
        return default


# ── measurement window ────────────────────────────────────────────────────────
# 28 days matches how Search Console reports and is long enough to smooth the
# weekday cycle without averaging away a post's actual trajectory.
WINDOW_DAYS = _i("LEARN_WINDOW_DAYS", 28)

# A post younger than this is not judged. SEO ramps over weeks — scoring a
# 3-day-old post against a 60-day-old one measures age, not quality, and would
# teach the engine that whatever it published last is always bad.
MIN_AGE_DAYS = _i("LEARN_MIN_AGE_DAYS", 14)

# ── outcome score weights (L1) ────────────────────────────────────────────────
# Impressions and clicks enter through log1p because the distribution is heavy-
# tailed: one post at 353 impressions should outrank one at 3 clearly, but not
# by 100x, or a single outlier becomes the entire training signal.
W_IMPRESSIONS = _f("LEARN_W_IMPRESSIONS", 1.0)
W_CLICKS = _f("LEARN_W_CLICKS", 2.0)      # a click is the outcome; an impression is only a chance at one
W_POSITION = _f("LEARN_W_POSITION", 1.5)
W_CTR = _f("LEARN_W_CTR", 1.0)
W_ENGAGEMENT = _f("LEARN_W_ENGAGEMENT", 0.5)

# Ranking below this is worth no credit — page 3 and page 30 are equally invisible.
POSITION_FLOOR = _f("LEARN_POSITION_FLOOR", 21.0)

# Roughly the CTR a mid-page-1 result earns. Used to normalise the CTR term so it
# lands on the same scale as the others; capped so one freak result cannot
# dominate the score.
CTR_BENCHMARK = _f("LEARN_CTR_BENCHMARK", 0.03)
CTR_CAP = _f("LEARN_CTR_CAP", 2.0)

# ── success definition (the bandit's reward) ──────────────────────────────────
# Deliberately coarse. The bandit learns from a binary outcome, and at this data
# volume a fine-grained reward would be fitting noise.
#
# A post succeeds if it earned a real click, or cleared an impression floor that
# separates "search found an audience" from "nobody saw it". Both are checked
# because clicks are still sparse at this traffic level — click-only would make
# almost every arm look like a failure and stall exploration.
SUCCESS_CLICKS = _i("LEARN_SUCCESS_CLICKS", 1)
SUCCESS_IMPRESSIONS = _i("LEARN_SUCCESS_IMPRESSIONS", 50)

# ── bandit ────────────────────────────────────────────────────────────────────
# Strength of the shrinkage prior, in pseudo-observations. Every arm starts at
# the site-wide success rate and needs real evidence to move away from it. This
# is what makes ~30 posts workable across ~20 arms: a one-post arm barely moves
# off the global mean instead of reporting 0% or 100%.
PRIOR_STRENGTH = _f("LEARN_PRIOR_STRENGTH", 4.0)

# Observations decay with this half-life, in days. Google changes, competitors
# publish, and the brand's own positioning moves — a win from a year ago is
# weaker evidence about today than one from last month.
DECAY_HALF_LIFE_DAYS = _f("LEARN_DECAY_HALF_LIFE_DAYS", 180.0)

# Posterior samples used for credible intervals and Thompson draws. 2000 is
# plenty for a chart and costs microseconds.
POSTERIOR_SAMPLES = _i("LEARN_POSTERIOR_SAMPLES", 2000)

# Below this many matured posts the bandit reports its beliefs but must not
# reorder the production queue. Its early posteriors are almost entirely prior,
# so acting on them would just be acting on the prior with extra steps.
MIN_POSTS_TO_ACT = _i("LEARN_MIN_POSTS_TO_ACT", 25)

# Master switch. Off by default: the bandit runs in shadow mode, visible on the
# dashboard, until its calibration has been checked against reality.
BANDIT_ACTIVE = os.environ.get("LEARN_BANDIT_ACTIVE", "false").strip().lower() == "true"


def snapshot() -> dict:
    """The exact configuration used by a run, stored alongside its results."""
    return {
        "window_days": WINDOW_DAYS,
        "min_age_days": MIN_AGE_DAYS,
        "weights": {
            "impressions": W_IMPRESSIONS, "clicks": W_CLICKS, "position": W_POSITION,
            "ctr": W_CTR, "engagement": W_ENGAGEMENT,
        },
        "position_floor": POSITION_FLOOR,
        "ctr_benchmark": CTR_BENCHMARK,
        "success": {"clicks": SUCCESS_CLICKS, "impressions": SUCCESS_IMPRESSIONS},
        "prior_strength": PRIOR_STRENGTH,
        "decay_half_life_days": DECAY_HALF_LIFE_DAYS,
        "min_posts_to_act": MIN_POSTS_TO_ACT,
        "bandit_active": BANDIT_ACTIVE,
    }
