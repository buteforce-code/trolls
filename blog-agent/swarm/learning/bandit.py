"""Layer 2 — Thompson Sampling over content arms.

Why a bandit and not deep RL: one blog post is one episode, and an episode costs
a day plus a month of waiting for the reward to mature. PPO-class algorithms need
10^4-10^6 episodes and a simulator to generate them; nothing can simulate how
Google will rank a page. Bandits are the stateless case of reinforcement
learning, and they are the part of it with useful regret bounds at *tens* of
observations rather than millions.

An arm is (cluster × source platform) — "manufacturing-cv from LinkedIn" — which
is the pairing the engine can actually act on when choosing what to write next.

Three properties make this work at ~30 posts across ~20 arms:

  1. Empirical-Bayes shrinkage. Every arm's prior is the site-wide success rate,
     worth PRIOR_STRENGTH pseudo-observations. An arm with one lucky post barely
     moves off the global mean, so a single outlier cannot capture the engine —
     the exact failure that a raw average would produce with one 353-impression
     post in the set.

  2. Time decay. Observations are weighted by a half-life, because Google, the
     competition and the brand's own positioning all move. Last year's win is
     weaker evidence about today than last month's.

  3. Uncertainty is the output, not a footnote. A wide posterior keeps an arm in
     exploration instead of writing it off, and the posterior draws as a curve —
     which is what makes the whole thing inspectable on a chart rather than a
     number to be taken on trust.

Deliberately dependency-free: `random.betavariate` and `math.lgamma` are stdlib,
so the posterior can be sampled and its density drawn without numpy or scipy on
a 256MB instance.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from swarm.learning import config
from swarm.learning.scorer import PostScore

# Points on the density curve the dashboard plots. 41 is smooth at chart size
# without bloating the stored JSON.
DENSITY_POINTS = 41


@dataclass
class Arm:
    arm: str
    cluster: str
    source_platform: str
    alpha: float
    beta: float
    trials: float          # fractional: observations are decay-weighted
    successes: float
    mean: float
    ci_low: float
    ci_high: float
    density: list[dict[str, float]] = field(default_factory=list)

    @property
    def uncertainty(self) -> float:
        return self.ci_high - self.ci_low


def _decay_weight(age_days: int | None) -> float:
    """Exponential decay by half-life. Older evidence counts for less."""
    if age_days is None or age_days <= 0:
        return 1.0
    return 0.5 ** (age_days / max(1.0, config.DECAY_HALF_LIFE_DAYS))


def _beta_pdf(x: float, alpha: float, beta: float) -> float:
    """Beta density via log-gamma, which stays finite where the direct form
    overflows once alpha or beta grows."""
    if x <= 0.0 or x >= 1.0:
        return 0.0
    log_b = math.lgamma(alpha) + math.lgamma(beta) - math.lgamma(alpha + beta)
    log_p = (alpha - 1) * math.log(x) + (beta - 1) * math.log(1 - x) - log_b
    return math.exp(log_p) if log_p > -700 else 0.0


def _density(alpha: float, beta: float) -> list[dict[str, float]]:
    """The curve the dashboard draws: the engine's belief about this arm."""
    step = 1.0 / (DENSITY_POINTS - 1)
    points = []
    for i in range(DENSITY_POINTS):
        x = min(max(i * step, 1e-4), 1 - 1e-4)
        points.append({"x": round(x, 4), "y": round(_beta_pdf(x, alpha, beta), 4)})
    return points


def _credible_interval(alpha: float, beta: float, rng: random.Random) -> tuple[float, float]:
    """90% credible interval by sampling.

    Sampling rather than inverting the incomplete beta function: it is a few
    lines instead of a numerical routine, exact enough for a chart, and needs no
    dependency. `random.betavariate` is stdlib.
    """
    samples = sorted(rng.betavariate(alpha, beta) for _ in range(config.POSTERIOR_SAMPLES))
    lo = samples[int(0.05 * len(samples))]
    hi = samples[int(0.95 * len(samples)) - 1]
    return round(lo, 6), round(hi, 6)


def global_success_rate(scores: Iterable[PostScore]) -> float:
    """Site-wide success rate over matured posts, Laplace-smoothed.

    This is the prior every arm starts from. With no matured posts at all it
    returns 0.5 — maximum ignorance, which is the honest starting belief.
    """
    matured = [s for s in scores if s.matured]
    if not matured:
        return 0.5
    successes = sum(1 for s in matured if s.success)
    return (successes + 1) / (len(matured) + 2)


def fit(scores: list[PostScore], seed: int | None = None) -> list[Arm]:
    """Build the posterior for every arm from scored posts.

    Only matured posts contribute. A post published last week has not had time to
    rank, so counting it as a failure would punish whichever arm happened to be
    used most recently.
    """
    rng = random.Random(seed if seed is not None else 12345)
    matured = [s for s in scores if s.matured]

    rate = global_success_rate(scores)
    prior_alpha = max(1e-6, rate * config.PRIOR_STRENGTH)
    prior_beta = max(1e-6, (1.0 - rate) * config.PRIOR_STRENGTH)

    grouped: dict[str, dict[str, float]] = {}
    labels: dict[str, tuple[str, str]] = {}
    for score in matured:
        slot = grouped.setdefault(score.arm, {"trials": 0.0, "successes": 0.0})
        labels[score.arm] = (score.cluster, score.source_platform or "unknown")
        weight = _decay_weight(score.age_days)
        slot["trials"] += weight
        if score.success:
            slot["successes"] += weight

    arms: list[Arm] = []
    for name, slot in grouped.items():
        cluster, platform = labels[name]
        alpha = prior_alpha + slot["successes"]
        beta = prior_beta + (slot["trials"] - slot["successes"])
        ci_low, ci_high = _credible_interval(alpha, beta, rng)
        arms.append(Arm(
            arm=name, cluster=cluster, source_platform=platform,
            alpha=round(alpha, 4), beta=round(beta, 4),
            trials=round(slot["trials"], 4), successes=round(slot["successes"], 4),
            mean=round(alpha / (alpha + beta), 6),
            ci_low=ci_low, ci_high=ci_high,
            density=_density(alpha, beta),
        ))

    arms.sort(key=lambda a: a.mean, reverse=True)
    return arms


def sample_arm(arm: Arm, rng: random.Random) -> float:
    """One Thompson draw: a plausible success rate given current belief.

    Ranking by these draws instead of by posterior means is the whole
    exploration mechanism. An uncertain arm sometimes draws high and gets tried;
    an arm that is confidently bad almost never does.
    """
    return rng.betavariate(max(1e-6, arm.alpha), max(1e-6, arm.beta))


def rank_candidates(
    candidates: list[dict],
    arms: list[Arm],
    prior_mean: float,
    seed: int | None = None,
) -> list[dict]:
    """Order queued topics by Thompson draw. Returns a decision record each.

    A candidate whose arm has never been observed is scored from the global
    prior, which leaves it genuinely uncertain — so new territory gets explored
    rather than being ranked last by default.
    """
    rng = random.Random(seed)
    by_name = {a.arm: a for a in arms}
    best_mean = max((a.mean for a in arms), default=prior_mean)

    ranked = []
    for candidate in candidates:
        name = candidate["arm"]
        arm = by_name.get(name)
        if arm is not None:
            sampled = sample_arm(arm, rng)
            mean, low, high, trials = arm.mean, arm.ci_low, arm.ci_high, arm.trials
        else:
            # Unobserved arm: sample from the bare prior.
            alpha = max(1e-6, prior_mean * config.PRIOR_STRENGTH)
            beta = max(1e-6, (1 - prior_mean) * config.PRIOR_STRENGTH)
            sampled = rng.betavariate(alpha, beta)
            mean, low, high, trials = prior_mean, 0.0, 1.0, 0.0

        # "Explore" means this pick was driven by uncertainty rather than by
        # evidence — the arm is not the current best, but its draw beat it.
        mode = "exploit" if mean >= best_mean - 1e-9 else "explore"

        ranked.append({
            **candidate,
            "sampled": round(sampled, 6),
            "arm_mean": mean,
            "arm_ci": [low, high],
            "arm_trials": trials,
            "mode": mode,
            "explanation": {
                "arm": name,
                "posterior_mean": mean,
                "credible_interval": [low, high],
                "observations": trials,
                "thompson_draw": round(sampled, 6),
                "reason": (
                    f"Arm {name!r} has {trials:.1f} weighted observations; the engine "
                    f"believes its success rate is {mean:.0%} (90% CI {low:.0%}-{high:.0%}). "
                    f"This draw came out at {sampled:.0%}."
                ),
            },
        })

    ranked.sort(key=lambda c: c["sampled"], reverse=True)
    for i, item in enumerate(ranked, 1):
        item["rank"] = i
    return ranked


def calibration(scores: list[PostScore], arms: list[Arm]) -> dict:
    """How well the arms' beliefs match what actually happened.

    Reported, never enforced. It is the number that decides whether the bandit
    has earned the right to reorder the queue — and it is deliberately visible on
    the dashboard so that decision is not taken on faith.
    """
    matured = [s for s in scores if s.matured]
    if not matured:
        return {"buckets": [], "brier": None, "n": 0}

    by_name = {a.arm: a for a in arms}
    pairs = [(by_name[s.arm].mean, 1.0 if s.success else 0.0)
             for s in matured if s.arm in by_name]
    if not pairs:
        return {"buckets": [], "brier": None, "n": 0}

    # Brier score: mean squared error of the probability forecast. 0 is perfect,
    # 0.25 is what always guessing 50% gets you.
    brier = sum((p - actual) ** 2 for p, actual in pairs) / len(pairs)

    buckets = []
    for low in (0.0, 0.2, 0.4, 0.6, 0.8):
        high = low + 0.2
        inside = [a for p, a in pairs if low <= p < high or (high == 1.0 and p == 1.0)]
        if inside:
            buckets.append({
                "range": f"{low:.0%}-{high:.0%}",
                "predicted": round((low + high) / 2, 3),
                "actual": round(sum(inside) / len(inside), 3),
                "n": len(inside),
            })

    return {"buckets": buckets, "brier": round(brier, 4), "n": len(pairs)}


def persist(db: Any, arms: list[Arm]) -> int:
    """Replace the stored posteriors with the freshly fitted ones."""
    if not arms:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    rows = [{
        "arm": a.arm, "cluster": a.cluster, "source_platform": a.source_platform,
        "alpha": a.alpha, "beta": a.beta, "trials": a.trials, "successes": a.successes,
        "mean": a.mean, "ci_low": a.ci_low, "ci_high": a.ci_high,
        "density": a.density, "updated_at": now,
    } for a in arms]
    db.table("bandit_arms").upsert(rows, on_conflict="arm").execute()
    return len(rows)
