"""The trend scout — sweep, gate, score, persist.

The pipeline that turns "what is happening in the world" into "what this brand
should write about", and records its reasoning at every step.

    sweep      pull raw signals from every configured source
    gate       drop anything the brand has no business writing about
    score      recency x engagement x relevance x headroom x novelty
    persist    store accepted AND rejected, with the reason

Rejected signals are kept on purpose. A scout that only records its hits cannot
be debugged: an empty topic queue looks identical whether nothing was happening
or the relevance gate was set too tight.

The gate matters more than the scoring. A live Google Trends pull returns Drake,
ENHYPEN and Tucson weather; without a hard relevance test those reach the ideator
and it will dutifully attempt to connect a K-pop story to industrial computer
vision. Relevance is checked first and is disqualifying, not a weight.
"""
from __future__ import annotations

import math
import re
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from swarm.learning.scorer import cluster_for
from swarm.trends import sources
from swarm.trends.sources import RawSignal

# Vocabulary the brand can credibly write about. A signal must hit at least one
# of these to survive. Kept explicit rather than delegated to an LLM: this runs
# over hundreds of signals per sweep, and a deterministic gate is free, instant
# and inspectable.
RELEVANT_TERMS = {
    # core capability
    "ai", "artificial intelligence", "machine learning", "computer vision", "cv",
    "llm", "genai", "generative ai", "neural", "model", "inference", "agent",
    "agents", "agentic", "automation", "ocr", "document ai", "rag", "embedding",
    # industry surface
    "manufacturing", "factory", "industrial", "production line", "quality control",
    "defect", "inspection", "warehouse", "logistics", "supply chain", "retail",
    "footfall", "cctv", "fmcg", "packaging", "robotics", "iot", "edge",
    # dev-tools / the Sarvam vertical
    "coding agent", "copilot", "developer tool", "code generation", "claude",
    "codex", "cursor", "openai", "anthropic", "gemini", "sarvam", "deepseek",
    "open source model", "fine-tune", "fine tune",
    # business surface
    "saas", "b2b", "roi", "cost", "pricing", "case study", "deployment",
    "enterprise ai", "ai adoption", "digital transformation",
}

# Signals that name these are almost always consumer noise from the Trends feed.
# Checked after relevance so a genuine story ("AI in sports broadcasting") is not
# lost — this only fires when nothing relevant matched.
NOISE_TERMS = {
    "vs", "match", "score", "live stream", "box office", "trailer", "episode",
    "weather", "lottery", "stock price", "election", "concert", "tour dates",
}

MIN_RELEVANCE = float(os.environ.get("TREND_MIN_RELEVANCE", "0.15"))
RECENCY_HALF_LIFE_HOURS = float(os.environ.get("TREND_RECENCY_HALF_LIFE", "72"))

# How far to trust each source, as a multiplier on its score. Measured, not
# assumed — see `_credibility()` for the ranked list this was derived from.
# First-party demand outranks the world's enthusiasm by construction.
_SOURCE_CREDIBILITY = {
    "gsc_rising":    1.00,
    "hacker_news":   0.70,
    "tavily_web":    0.55,
    "tavily_linkedin": 0.55,
    "tavily_reddit": 0.55,
    "google_trends": 0.15,
}
# An unrecognised source is treated as a targeted search rather than as noise:
# a new adapter is far more likely to be deliberate than to be a consumer feed,
# and under-weighting a good new source is the quieter failure of the two.
_DEFAULT_CREDIBILITY = 0.55

# Word-boundary matching, not substring.
#
# The first live sweep let "tucson weather" and "flight" through the gate,
# because plain `"ai" in text` matches inside r-ai-nfall, -ai-r and s-ai-d. Short
# terms like "ai", "cv" and "iot" are exactly the ones that must be precise, and
# they are unavoidable in this vocabulary. `\b` on both ends fixes it without
# losing multi-word phrases like "computer vision".
_TERM_RE = re.compile(
    r"\b(" + "|".join(sorted((re.escape(t) for t in RELEVANT_TERMS), key=len, reverse=True)) + r")\b"
)
_NOISE_RE = re.compile(
    r"\b(" + "|".join(sorted((re.escape(t) for t in NOISE_TERMS), key=len, reverse=True)) + r")\b"
)


@dataclass
class ScoredSignal:
    raw: RawSignal
    relevance: float
    score: float
    components: dict[str, float]
    cluster: str
    status: str           # 'new' | 'rejected'
    reject_reason: str = ""


def _text(signal: RawSignal) -> str:
    return f"{signal.title} {signal.summary}".lower()


def relevance_of(signal: RawSignal) -> tuple[float, str]:
    """Fraction of the brand vocabulary the signal touches, plus a reason.

    Normalised by a small constant rather than by vocabulary size: a signal
    matching three terms is decisively relevant, and dividing by ~90 terms would
    make everything score near zero.
    """
    text = _text(signal)

    # First-party search demand is relevant by construction — it is a query that
    # already reached this site. No vocabulary test can improve on that.
    if signal.source == "gsc_rising":
        return 1.0, "first-party search demand"

    hits = sorted(set(_TERM_RE.findall(text)))
    if not hits:
        noise = _NOISE_RE.search(text)
        return 0.0, f"no brand vocabulary{'; consumer noise' if noise else ''}"

    # A single bare "ai" is the weakest possible evidence — it appears in almost
    # any technology-adjacent headline. Require either a second term or one that
    # is specific on its own.
    if len(hits) == 1 and hits[0] in {"ai", "model", "agent", "agents", "cost"}:
        return 0.1, f"only a generic term ({hits[0]})"

    return min(1.0, len(hits) / 4.0), f"matched {', '.join(hits[:4])}"


def _recency(signal: RawSignal, now: datetime) -> float:
    """1.0 for something happening now, halving every RECENCY_HALF_LIFE_HOURS.

    Steep by design. The Sarvam post earned its traffic because it was published
    while the story was forming; the same post two weeks later competes with
    everyone else's coverage.
    """
    if not signal.published_at:
        return 0.5
    hours = max(0.0, (now - signal.published_at).total_seconds() / 3600.0)
    return 0.5 ** (hours / RECENCY_HALF_LIFE_HOURS)


def _engagement(signal: RawSignal) -> float:
    """Log-damped, so one enormous thread does not outweigh everything else."""
    return min(1.0, math.log1p(max(0.0, signal.engagement)) / math.log1p(1000.0))


def _credibility(signal: RawSignal) -> float:
    """How much this source's enthusiasm is worth to *this* brand.

    Added 2026-09-03, after measuring what the top of the list actually contained.
    The scoring was relevance x recency x engagement x novelty, with no term for
    where the signal came from — so a mass-consumer spike with perfect recency and
    huge engagement outscored a first-party Search Console query almost every time.

    The list the ideator was handed, ranked:

        66.7  google_trends  "fable 5.1"
        43.7  google_trends  "booking"
        41.0  gsc_rising     "sarvam code"                 <- the only real win
        38.2  google_trends  "independence day 2026 photo"
        28.2  gsc_rising     "machine vision companies in india"
        24.9  google_trends  "gold rate today mumbai"

    Both of this site's genuine wins came from `gsc_rising`, and every Trends
    entry above is noise that cleared the relevance gate on a single keyword.
    `sources.py` has said since it was written that Trends RSS is "close to
    worthless for a B2B industrial-AI brand"; this is the line that makes the
    ranking agree with the docstring.

    Multiplicative, like the other terms, because credibility is not a bonus to
    be outbid — a viral consumer story is still a viral consumer story no matter
    how much engagement it has.

      gsc_rising    first-party. Demand from this audience, already measured,
                    arriving at the door and bouncing. Nothing beats it.
      hacker_news   where AI and dev-tool stories break, with real engagement,
                    days early. This is the source that caught Sarvam.
      tavily_*      targeted LinkedIn/Reddit/web search — asked for, not swept up.
      google_trends kept because it is free and occasionally a large tech story
                    trends, but priced at what it has actually been worth.
    """
    return _SOURCE_CREDIBILITY.get(signal.source, _DEFAULT_CREDIBILITY)


def _novelty(signal: RawSignal, existing_titles: set[str]) -> tuple[float, str]:
    """0.0 if the site already covers this ground."""
    words = {w for w in _text(signal).split() if len(w) > 4}
    if not words:
        return 0.5, ""
    for title in existing_titles:
        title_words = {w for w in title.lower().split() if len(w) > 4}
        if not title_words:
            continue
        overlap = len(words & title_words) / max(1, min(len(words), len(title_words)))
        if overlap > 0.6:
            return 0.0, f"overlaps existing post: {title[:60]}"
    return 1.0, ""


def score_signal(signal: RawSignal, existing_titles: set[str],
                 now: datetime | None = None) -> ScoredSignal:
    """Gate then score one signal. Pure — no I/O, so it is directly testable."""
    now = now or datetime.now(timezone.utc)
    relevance, reason = relevance_of(signal)
    cluster = cluster_for([], f"{signal.title} {signal.summary}")

    if relevance < MIN_RELEVANCE:
        return ScoredSignal(
            raw=signal, relevance=relevance, score=0.0,
            components={}, cluster=cluster, status="rejected",
            reject_reason=f"relevance {relevance:.2f} below {MIN_RELEVANCE} ({reason})",
        )

    novelty, novelty_reason = _novelty(signal, existing_titles)
    if novelty == 0.0:
        return ScoredSignal(
            raw=signal, relevance=relevance, score=0.0,
            components={}, cluster=cluster, status="rejected",
            reject_reason=novelty_reason,
        )

    components = {
        "relevance": round(relevance, 4),
        "recency": round(_recency(signal, now), 4),
        "engagement": round(_engagement(signal), 4),
        "novelty": round(novelty, 4),
        "credibility": round(_credibility(signal), 4),
    }
    # Multiplicative, not additive: a signal must be relevant AND timely AND
    # discussed AND come from somewhere worth listening to. Summing would let a
    # stale but heavily-upvoted story outrank a breaking one, which is backwards
    # for newsjacking — and would let consumer-trend volume buy its way past a
    # first-party query, which is how "gold rate today mumbai" outranked
    # "machine vision companies in india".
    score = 1.0
    for value in components.values():
        score *= max(0.01, value)

    return ScoredSignal(
        raw=signal, relevance=relevance, score=round(score * 100, 4),
        components=components, cluster=cluster, status="new",
    )


# ── sweep ─────────────────────────────────────────────────────────────────────
def sweep(db: Any, log: list[str] | None = None) -> list[RawSignal]:
    """Pull from every configured source. A failing source is reported, not fatal."""
    log = log if log is not None else []
    collected: list[RawSignal] = []

    for name, fetch in (
        ("hacker_news", lambda: sources.hacker_news()),
        ("gsc_rising", lambda: sources.gsc_rising(db)),
        ("google_trends", lambda: sources.google_trends_rss()),
        ("paid_trends", lambda: sources.paid_trends_provider()),
    ):
        try:
            found = fetch()
            collected.extend(found)
            log.append(f"  {name}: {len(found)} raw signals")
        except NotImplementedError as exc:
            log.append(f"  {name}: not configured ({exc})")
        except Exception as exc:
            log.append(f"  ! {name} FAILED: {exc}")
    return collected


def run_scout(db: Any, limit: int = 200) -> list[str]:
    """One full sweep: fetch, gate, score, persist. Returns a log."""
    log = [f"[scout] sweep @ {datetime.now(timezone.utc).isoformat()}"]

    raw = sweep(db, log)
    if not raw:
        log.append("  no signals from any source")
        return log

    topics = db.table("topics").select("title").limit(2000).execute().data or []
    existing = {t["title"] for t in topics if t.get("title")}

    # Deduplicate within the sweep before scoring — the same story often appears
    # under several HN queries.
    unique: dict[str, RawSignal] = {}
    for signal in raw:
        unique.setdefault(signal.fingerprint, signal)

    scored = [score_signal(s, existing) for s in unique.values()]
    accepted = sorted([s for s in scored if s.status == "new"],
                      key=lambda s: s.score, reverse=True)
    rejected = [s for s in scored if s.status == "rejected"]

    log.append(f"  {len(unique)} unique signals -> {len(accepted)} passed the gate, "
               f"{len(rejected)} rejected")

    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for item in (accepted + rejected)[:limit]:
        signal = item.raw
        rows.append({
            "fingerprint": signal.fingerprint,
            "source": signal.source, "platform": signal.platform, "geo": signal.geo,
            "title": signal.title[:500], "url": signal.url[:800],
            "summary": signal.summary[:1000], "engagement": signal.engagement,
            "last_seen": now,
            "published_at": signal.published_at.isoformat() if signal.published_at else None,
            "relevance": item.relevance, "score": item.score,
            "components": item.components, "cluster": item.cluster,
            "status": item.status, "reject_reason": item.reject_reason[:400],
            "raw": signal.raw,
        })

    written = 0
    for i in range(0, len(rows), 200):
        try:
            db.table("scout_signals").upsert(rows[i:i + 200], on_conflict="fingerprint").execute()
            written += len(rows[i:i + 200])
        except Exception as exc:
            log.append(f"  ! persist failed: {exc}")
    log.append(f"  stored {written} signals (accepted and rejected both kept)")

    for item in accepted[:8]:
        log.append(f"    {item.score:>7.2f}  [{item.cluster}] {item.raw.title[:56]}")

    log.append("[scout] done")
    return log


def top_signals(db: Any, limit: int = 12) -> list[dict]:
    """Highest-scoring unused signals, for the ideator to build topics from."""
    return (db.table("scout_signals")
            .select("fingerprint,source,platform,title,url,summary,score,cluster,geo,components")
            .eq("status", "new").is_("topic_slug", "null")
            .order("score", desc=True).limit(limit).execute().data or [])
