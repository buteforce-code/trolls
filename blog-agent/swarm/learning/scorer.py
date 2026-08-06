"""Layer 1 — the deterministic outcome scorer.

Turns 28 days of search and engagement data into one comparable number per post,
plus the breakdown of how that number was reached. Readable on purpose: at the
current data volume the honest thing is a formula a human can argue with, not a
model that cannot be questioned.

It also produces the binary reward the bandit learns from, so both layers agree
on what "this post worked" means.

Two rules do most of the work:

  * Immature posts are not scored. SEO ramps over weeks, so scoring a 3-day-old
    post next to a 60-day-old one measures age. They are carried through with
    `matured=False` and excluded from every average and every arm update.

  * Counts enter through log1p. One post at 353 impressions should clearly beat
    one at 3 — but not by 100x, or that single post becomes the whole signal.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from swarm.learning import config

# Tag → cluster. The bandit needs a small, stable set of arms; raw tags are too
# many and too inconsistent to learn from. Order matters — first match wins.
CLUSTER_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("manufacturing-cv", ("computer-vision", "quality-control", "manufacturing",
                          "defect-detection", "fmcg", "inspection")),
    ("retail-cv", ("retail", "footfall", "zone-analytics", "cctv")),
    ("document-ai", ("ocr", "document-ai", "documents", "invoice")),
    ("ai-agents", ("ai-agents", "agents", "lead-qualification", "customer-support", "chatbot")),
    ("automation", ("workflow", "automation", "n8n", "integration")),
    ("dev-tools", ("coding-agent", "developer-tools", "llm", "ai-coding", "claude", "codex")),
    ("ecosystem", ("chennai", "tamil-nadu", "india", "indiaai", "policy", "ecosystem", "seo")),
]
DEFAULT_CLUSTER = "other"


def cluster_for(tags: list[str] | None, title: str = "") -> str:
    """Map a topic's tags onto the fixed cluster taxonomy.

    Falls back to matching the title when tags are missing or unhelpful, because
    an unclustered post is invisible to the bandit rather than merely uncertain.
    """
    haystack = " ".join([*(tags or []), title]).lower().replace("_", "-")
    for cluster, needles in CLUSTER_RULES:
        if any(needle in haystack for needle in needles):
            return cluster
    return DEFAULT_CLUSTER


@dataclass
class PostScore:
    slug: str
    cluster: str
    source_kind: str | None
    source_platform: str | None
    age_days: int | None
    matured: bool
    content_format: str | None = None
    impressions: int = 0
    clicks: int = 0
    ctr: float | None = None
    position: float | None = None
    views: int = 0
    engagement_rate: float | None = None
    outcome_score: float = 0.0
    success: bool = False
    components: dict[str, float] = field(default_factory=dict)

    @property
    def arm(self) -> str:
        """The bandit arm this post belongs to.

        Format joins the key only when LEARN_FORMAT_ARMS is on. Splitting a
        ~6-arm space by six formats at 10 matured posts would leave almost every
        cell under one observation, and a posterior fitted to that is the prior
        with extra steps — see learning/formats.py.
        """
        from swarm.learning.formats import FORMAT_ARMS

        base = f"{self.cluster}:{self.source_platform or 'unknown'}"
        return f"{base}:{self.content_format or 'unknown'}" if FORMAT_ARMS else base


def _position_quality(position: float | None) -> float:
    """0.0 → 1.0. Rank 1 is worth 1.0; anything past the floor is worth nothing,
    because page 3 and page 30 are equally invisible."""
    if position is None or position <= 0:
        return 0.0
    if position >= config.POSITION_FLOOR:
        return 0.0
    return (config.POSITION_FLOOR - position) / (config.POSITION_FLOOR - 1.0)


def score_one(
    slug: str,
    cluster: str,
    source_kind: str | None,
    source_platform: str | None,
    age_days: int | None,
    impressions: int,
    clicks: int,
    position: float | None,
    views: int,
    engagement_rate: float | None,
    content_format: str | None = None,
) -> PostScore:
    """Score one post. Pure — no I/O — so it is directly testable."""
    ctr = (clicks / impressions) if impressions else None
    matured = age_days is not None and age_days >= config.MIN_AGE_DAYS

    components = {
        "impressions": round(config.W_IMPRESSIONS * math.log1p(impressions), 4),
        "clicks": round(config.W_CLICKS * math.log1p(clicks), 4),
        "position": round(config.W_POSITION * _position_quality(position), 4),
        "ctr": round(
            config.W_CTR * min((ctr or 0.0) / config.CTR_BENCHMARK, config.CTR_CAP), 4
        ),
        "engagement": round(config.W_ENGAGEMENT * (engagement_rate or 0.0), 4),
    }

    success = clicks >= config.SUCCESS_CLICKS or impressions >= config.SUCCESS_IMPRESSIONS

    return PostScore(
        slug=slug, cluster=cluster, source_kind=source_kind, source_platform=source_platform,
        age_days=age_days, matured=matured, content_format=content_format,
        impressions=impressions, clicks=clicks,
        ctr=round(ctr, 6) if ctr is not None else None,
        position=round(position, 2) if position is not None else None,
        views=views,
        engagement_rate=round(engagement_rate, 6) if engagement_rate is not None else None,
        outcome_score=round(sum(components.values()), 4),
        success=success,
        components=components,
    )


# ── data assembly ─────────────────────────────────────────────────────────────
def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def score_all(db: Any) -> list[PostScore]:
    """Score every published post from the stored metrics."""
    cutoff = (date.today() - timedelta(days=config.WINDOW_DAYS)).isoformat()
    now = datetime.now(timezone.utc)

    topics = (db.table("topics")
              .select("id,slug,title,tags,status,source_kind,source_detail,content_format")
              .eq("status", "published").limit(5000).execute().data or [])
    if not topics:
        return []

    posts = (db.table("blog_posts").select("topic_id,published_at")
             .limit(5000).execute().data or [])
    published_at = {}
    slug_by_id = {t["id"]: t["slug"] for t in topics}
    for post in posts:
        slug = slug_by_id.get(post.get("topic_id"))
        if slug and post.get("published_at"):
            published_at[slug] = _parse_dt(post["published_at"])

    metrics = (db.table("post_metrics_daily")
               .select("slug,source,impressions,clicks,position,views,engagement_rate")
               .gte("date", cutoff).limit(100000).execute().data or [])

    # Impression-weighted for position, view-weighted for engagement rate — both
    # are per-unit averages, so summing them requires the same weighting the
    # ingester applies when folding URLs together.
    agg: dict[str, dict[str, float]] = {}
    for row in metrics:
        slot = agg.setdefault(row["slug"], {
            "impressions": 0.0, "clicks": 0.0, "pos_weight": 0.0,
            "views": 0.0, "er_weight": 0.0,
        })
        if row.get("source") == "gsc":
            impressions = float(row.get("impressions") or 0)
            slot["impressions"] += impressions
            slot["clicks"] += float(row.get("clicks") or 0)
            slot["pos_weight"] += float(row.get("position") or 0) * impressions
        elif row.get("source") == "ga4":
            views = float(row.get("views") or 0)
            slot["views"] += views
            slot["er_weight"] += float(row.get("engagement_rate") or 0) * views

    scores: list[PostScore] = []
    for topic in topics:
        slug = topic["slug"]
        slot = agg.get(slug, {})
        impressions = int(slot.get("impressions", 0))
        views = int(slot.get("views", 0))
        pub = published_at.get(slug)
        detail = topic.get("source_detail") or {}
        if isinstance(detail, str):
            detail = {}

        scores.append(score_one(
            slug=slug,
            cluster=cluster_for(topic.get("tags"), topic.get("title", "")),
            source_kind=topic.get("source_kind"),
            source_platform=detail.get("platform"),
            content_format=topic.get("content_format"),
            age_days=(now - pub).days if pub else None,
            impressions=impressions,
            clicks=int(slot.get("clicks", 0)),
            position=(slot["pos_weight"] / impressions) if impressions else None,
            views=views,
            engagement_rate=(slot["er_weight"] / views) if views else None,
        ))

    scores.sort(key=lambda s: s.outcome_score, reverse=True)
    return scores


def persist(db: Any, scores: list[PostScore]) -> int:
    """Upsert scores. One row per post — history lives in learning_snapshots."""
    if not scores:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for s in scores:
        row = asdict(s)
        row["computed_at"] = now
        row["window_days"] = config.WINDOW_DAYS
        rows.append(row)
    db.table("post_scores").upsert(rows, on_conflict="slug").execute()
    return len(rows)
