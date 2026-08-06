"""The learning run: score → fit → rank → record.

Called nightly after analytics ingestion. Everything it writes is read by the
/learning dashboard, so what the engine believes and what you see are the same
computation rather than two implementations that can drift apart.

Shadow mode is the default and the point. The bandit records what it *would*
have chosen and how confident it was, but does not touch the production queue
until it has both enough matured posts (MIN_POSTS_TO_ACT) and an explicit switch
(LEARN_BANDIT_ACTIVE). A model that starts steering on its third data point is
steering on its prior.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from swarm.learning import bandit, config, scorer

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _queued_candidates(db: Any) -> list[dict]:
    """Queued topics, shaped for ranking."""
    rows = (db.table("topics")
            .select("slug,title,tags,source_kind,source_detail,created_at")
            .eq("status", "queued").limit(2000).execute().data or [])
    candidates = []
    for row in rows:
        detail = row.get("source_detail") or {}
        if isinstance(detail, str):
            detail = {}
        cluster = scorer.cluster_for(row.get("tags"), row.get("title", ""))
        platform = detail.get("platform") or "unknown"
        candidates.append({
            "slug": row["slug"],
            "title": row.get("title", ""),
            "cluster": cluster,
            "source_platform": platform,
            "arm": f"{cluster}:{platform}",
            "created_at": row.get("created_at"),
        })
    return candidates


def _record_decisions(db: Any, ranked: list[dict], applied: bool, log: list[str]) -> int:
    """Append this run's ranking to the decision log.

    Appended rather than replaced: the value of the log is watching beliefs
    change over time, which a table that only holds the latest opinion cannot
    show.
    """
    if not ranked:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    rows = [{
        "at": now, "slug": item["slug"], "arm": item["arm"], "mode": item["mode"],
        "rank": item["rank"], "l1_score": None, "sampled": item["sampled"],
        "explanation": item["explanation"], "applied": applied,
    } for item in ranked[:50]]
    try:
        db.table("topic_decisions").insert(rows).execute()
    except Exception as exc:
        log.append(f"  ! could not record decisions: {exc}")
        return 0
    return len(rows)


def _write_signals_markdown(scores: list[scorer.PostScore], arms: list[bandit.Arm],
                            log: list[str]) -> None:
    """Write measured signals to `config/gsc-signals-generated.md`.

    Deliberately a *separate* file from the hand-written `gsc-signals.md`, which
    both are loaded into the Ideator and Research prompts.

    The hand-written one holds things measurement cannot produce: competitor
    analysis, and the real defect-level vocabulary FMCG buyers search with
    ("unsealed sachet detection", "fill-level inspection"). None of that is
    derivable from a Search Console export — it came from somebody reading the
    market. Generating over it would quietly destroy research and replace it
    with a table of numbers.

    So: measurement refreshes itself here, human insight stays where a human put
    it, and the prompt gets both.
    """
    matured = [s for s in scores if s.matured]
    if not matured:
        log.append("  signals: no matured posts — nothing measured to write")
        return

    ranked = sorted(matured, key=lambda s: s.outcome_score, reverse=True)
    with_traffic = [s for s in ranked if s.impressions > 0]
    losers = [s for s in ranked[-5:] if s.outcome_score < ranked[0].outcome_score]
    page_two = [s for s in matured if s.position and 10 < s.position <= 20 and s.impressions >= 10]
    today = datetime.now(timezone.utc).date().isoformat()

    lines = [
        f"# Measured Signals — generated {today}",
        "",
        "> GENERATED FILE. Written by `swarm/learning/engine.py` from Search Console and GA4",
        "> data on every learning run. Hand edits here are overwritten — put durable insight",
        "> in `gsc-signals.md` (which is never generated over), and change scoring weights in",
        "> `swarm/learning/config.py`.",
        "",
        f"Based on **{len(matured)} matured posts** (published at least "
        f"{config.MIN_AGE_DAYS} days ago), measured over the last {config.WINDOW_DAYS} days.",
        "",
        "## What is working",
        "",
    ]

    if not with_traffic:
        # Ranking posts by score when every score is zero would present the
        # alphabetically-luckiest post as a proven winner, and this text is read
        # by the Ideator as evidence. Say nothing instead of something false.
        lines += [
            "**No post has recorded a single search impression yet.** Either analytics "
            "ingestion has not run, or these posts genuinely have no search visibility.",
            "",
            "Draw no conclusions from this section until it lists real numbers. Fall back to "
            "the curated market knowledge and the strategy clusters.",
        ]
    else:
        for s in with_traffic[:5]:
            lines.append(
                f"- **{s.slug}** — {s.impressions} impressions, {s.clicks} clicks, "
                f"position {s.position if s.position else '—'}. "
                f"Cluster `{s.cluster}`, sourced from `{s.source_platform or 'unknown'}`."
            )

    if losers and with_traffic:
        lines += ["", "## What is not", ""]
        for s in losers:
            lines.append(
                f"- **{s.slug}** — {s.impressions} impressions, {s.clicks} clicks. "
                f"Cluster `{s.cluster}`."
            )

    if page_two:
        lines += [
            "", "## Highest-ROI fixes (page 2, demand already proven)", "",
            "A page-2 page with impressions needs a title/meta rewrite and more depth, "
            "not a new backlink:", "",
        ]
        for s in sorted(page_two, key=lambda x: x.impressions, reverse=True)[:5]:
            lines.append(f"- **{s.slug}** — position {s.position}, {s.impressions} impressions")

    if arms:
        lines += ["", "## Measured performance by cluster and source", "",
                  "| Arm | Success rate | 90% CI | Observations |", "|---|---|---|---|"]
        for a in arms[:12]:
            lines.append(
                f"| `{a.arm}` | {a.mean:.0%} | {a.ci_low:.0%}–{a.ci_high:.0%} | {a.trials:.1f} |"
            )
        lines += [
            "",
            "> A wide interval means too little evidence to act on, not a bad arm. Arms with "
            "few observations are still worth exploring.",
        ]

    lines += [
        "", "## How to use this", "",
        "1. Prefer clusters with a high success rate **and** a narrow interval — those are proven.",
        "2. Treat wide-interval arms as worth testing, not worth avoiding.",
        "3. Fix the page-2 pages above before opening a new cluster: the demand is already there.",
        "4. Write to the defect-level long tail the query data shows, not the generic phrase.",
        "",
    ]

    target = _CONFIG_DIR / "gsc-signals-generated.md"
    try:
        target.write_text("\n".join(lines), encoding="utf-8")
        log.append(f"  signals: wrote {target.name} from {len(matured)} matured posts")
    except Exception as exc:
        log.append(f"  ! could not write {target}: {exc}")


def run_learning(db: Any, seed: int | None = None) -> list[str]:
    """One learning pass. Returns a human-readable log."""
    log = [f"[learning] run @ {datetime.now(timezone.utc).isoformat()}"]

    # Classify formats before scoring, so every score carries the format the post
    # was written in. The bandit does not split arms by format yet (see
    # learning/formats.py on why), but the column has to be filled from now on or
    # there will be nothing to learn from when it can.
    from swarm.learning import formats

    log.extend(formats.backfill(db))

    scores = scorer.score_all(db)
    if not scores:
        log.append("  no published posts — nothing to learn from")
        return log

    matured = [s for s in scores if s.matured]
    log.append(f"  scored {len(scores)} posts ({len(matured)} matured, "
               f"{len(scores) - len(matured)} still ramping)")
    scorer.persist(db, scores)

    arms = bandit.fit(scores, seed=seed)
    rate = bandit.global_success_rate(scores)
    bandit.persist(db, arms)
    log.append(f"  fitted {len(arms)} arms; site-wide success rate {rate:.0%}")

    for arm in arms[:5]:
        log.append(f"    {arm.arm:<34} {arm.mean:.0%} "
                   f"[{arm.ci_low:.0%}-{arm.ci_high:.0%}] n={arm.trials:.1f}")

    candidates = _queued_candidates(db)
    ranked = bandit.rank_candidates(candidates, arms, rate, seed=seed)

    # Two independent gates. Enough evidence, and an explicit human decision to
    # let it steer. Either one missing means shadow mode.
    enough = len(matured) >= config.MIN_POSTS_TO_ACT
    applied = enough and config.BANDIT_ACTIVE
    if not enough:
        log.append(f"  SHADOW MODE — {len(matured)}/{config.MIN_POSTS_TO_ACT} matured posts "
                   "needed before the bandit may reorder the queue")
    elif not config.BANDIT_ACTIVE:
        log.append("  SHADOW MODE — enough data, but LEARN_BANDIT_ACTIVE is not true")
    else:
        log.append("  ACTIVE — the bandit is ordering the production queue")

    recorded = _record_decisions(db, ranked, applied, log)
    log.append(f"  ranked {len(ranked)} queued topics, recorded {recorded} decisions")
    if ranked:
        top = ranked[0]
        log.append(f"    next up: {top['slug']} ({top['mode']}, arm {top['arm']}, "
                   f"draw {top['sampled']:.0%})")

    cal = bandit.calibration(scores, arms)
    if cal.get("brier") is not None:
        log.append(f"  calibration: Brier {cal['brier']} over {cal['n']} posts "
                   f"(0 perfect, 0.25 = always guessing 50%)")

    try:
        db.table("learning_snapshots").insert({
            "at": datetime.now(timezone.utc).isoformat(),
            "posts_scored": len(scores), "posts_matured": len(matured),
            "arms": len(arms), "global_rate": round(rate, 6),
            "calibration": cal, "config": config.snapshot(),
        }).execute()
    except Exception as exc:
        log.append(f"  ! could not write snapshot: {exc}")

    _write_signals_markdown(scores, arms, log)

    log.append("[learning] done")
    return log


def next_queued_slug(db: Any) -> str | None:
    """The slug the learning layer recommends producing next, or None.

    Returns None unless the bandit is genuinely active, so the autopilot's
    existing FIFO order stays in force during shadow mode. The caller decides;
    this only offers an opinion.
    """
    if not config.BANDIT_ACTIVE:
        return None
    rows = (db.table("topic_decisions").select("slug,at,rank,applied")
            .eq("applied", True).order("at", desc=True).limit(200)
            .execute().data or [])
    if not rows:
        return None

    # Only the most recent ranking counts, walked best-rank first. The rows come
    # back newest-first but in arbitrary rank order within a batch, so ordering
    # here is what makes "the top pick" mean anything.
    latest = rows[0]["at"]
    batch = sorted((r for r in rows if r["at"] == latest),
                   key=lambda r: r.get("rank") or 1_000_000)

    for row in batch:
        # Confirm it is still queued — the decision log is a historical record
        # and the topic may have been produced or cancelled since.
        status = (db.table("topics").select("status").eq("slug", row["slug"])
                  .limit(1).execute().data or [])
        if status and status[0]["status"] == "queued":
            return row["slug"]
    return None
