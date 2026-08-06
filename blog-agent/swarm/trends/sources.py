"""Trend sources — where the scout looks for what is moving.

Each source is a function returning `list[RawSignal]`. They fail independently:
one source being rate-limited or restructured must not cost you the sweep, so a
broken source is reported and skipped rather than raised.

WHAT ACTUALLY WORKS, measured 2026-08-06 against the live endpoints
-------------------------------------------------------------------
`pytrends` (the usual answer for "Google Trends API") returns HTTP 429 on the
very first call. Google has closed the unofficial endpoint; it is not a rate
limit you can wait out. There is no working free Trends API — the official one
is allowlist-only alpha, and the reliable alternatives (SerpApi, DataForSEO) are
paid. `TRENDS_PROVIDER` exists so one of those drops in without touching the
scout.

The Trends *daily RSS* feed does still work and is wired in, but be clear-eyed
about it: a live US pull returned ENHYPEN, Drake, Ubisoft, Aubrey Plaza and
Tucson weather. It surfaces mass-consumer spikes, which is close to worthless for
a B2B industrial-AI brand. It is kept because it is free and occasionally a
genuinely large tech story trends — but it is gated hard on relevance, and it is
not where the value is.

The value is in the other three:
  * Hacker News   — where AI/dev-tool stories break, with real engagement
                    numbers, days before anything else notices. This is the
                    source that would have caught Sarvam.
  * GSC rising    — first-party. Queries where the site is *already* getting
                    impressions but ranks badly. Better than any third-party
                    trend signal because it is this audience, not the world's.
  * Tavily        — LinkedIn/Reddit/web, already used by the ideator.
"""
from __future__ import annotations

import hashlib
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

TRENDS_RSS = "https://trends.google.com/trending/rss"
HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date"
TIMEOUT = 30
HT_NS = {"ht": "https://trends.google.com/trending/rss"}


@dataclass
class RawSignal:
    source: str
    platform: str
    title: str
    url: str = ""
    summary: str = ""
    engagement: float = 0.0
    geo: str = ""
    published_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """Stable id for the same story seen again on a later sweep.

        Keyed on source + normalised title rather than URL: the same story is
        routinely syndicated to several URLs, and counting it twice would inflate
        it into a bigger trend than it is.
        """
        key = f"{self.source}|{re.sub(r'[^a-z0-9]+', '', self.title.lower())}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_rfc822(value: str) -> datetime | None:
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _parse_traffic(value: str | None) -> float:
    """'1000+' -> 1000.0. Google reports approximate bands, not counts."""
    if not value:
        return 0.0
    digits = re.sub(r"[^\d]", "", value)
    return float(digits) if digits else 0.0


# ── Google Trends (daily RSS) ─────────────────────────────────────────────────
def google_trends_rss(geos: list[str] | None = None) -> list[RawSignal]:
    """Daily trending searches per geo.

    Geos are configurable via `TRENDS_GEOS` (comma-separated ISO codes) so the
    same sweep can watch India and the US, or anywhere else, without a code
    change.
    """
    geos = geos or [g.strip().upper() for g in
                    os.environ.get("TRENDS_GEOS", "IN,US").split(",") if g.strip()]
    signals: list[RawSignal] = []

    for geo in geos:
        try:
            resp = requests.get(TRENDS_RSS, params={"geo": geo}, timeout=TIMEOUT)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception as exc:
            raise RuntimeError(f"Google Trends RSS failed for geo {geo}: {exc}") from exc

        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            news = item.find(".//ht:news_item_title", HT_NS)
            news_url = item.find(".//ht:news_item_url", HT_NS)
            signals.append(RawSignal(
                source="google_trends",
                platform="google_trends",
                title=title,
                url=(news_url.text or "") if news_url is not None else "",
                summary=(news.text or "") if news is not None else "",
                engagement=_parse_traffic(item.findtext("ht:approx_traffic", namespaces=HT_NS)),
                geo=geo,
                published_at=_parse_rfc822(item.findtext("pubDate") or ""),
                raw={"geo": geo},
            ))
    return signals


# ── Hacker News ───────────────────────────────────────────────────────────────
DEFAULT_HN_QUERIES = [
    "AI coding agent", "computer vision", "OCR document AI",
    "manufacturing automation", "AI agents production", "LLM inference edge",
]


def hacker_news(queries: list[str] | None = None, min_points: int = 20,
                days: int = 14) -> list[RawSignal]:
    """Recent HN stories above an engagement floor.

    Engagement is `points + 2*comments`: a heated comment thread signals a topic
    people have opinions about, which converts to search demand more reliably
    than quiet upvotes on a link nobody argued over.
    """
    queries = queries or DEFAULT_HN_QUERIES
    since = int((_now() - timedelta(days=days)).timestamp())
    signals: list[RawSignal] = []
    seen: set[str] = set()

    for query in queries:
        try:
            resp = requests.get(HN_SEARCH, params={
                "query": query, "tags": "story",
                "numericFilters": f"points>{min_points},created_at_i>{since}",
                "hitsPerPage": 25,
            }, timeout=TIMEOUT)
            resp.raise_for_status()
            hits = (resp.json() or {}).get("hits") or []
        except Exception as exc:
            raise RuntimeError(f"Hacker News search failed for {query!r}: {exc}") from exc

        for hit in hits:
            title = (hit.get("title") or "").strip()
            if not title or hit.get("objectID") in seen:
                continue
            seen.add(hit.get("objectID"))
            points = float(hit.get("points") or 0)
            comments = float(hit.get("num_comments") or 0)
            signals.append(RawSignal(
                source="hacker_news",
                platform="hacker_news",
                title=title,
                url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                summary=(hit.get("story_text") or "")[:500],
                engagement=points + 2 * comments,
                geo="GLOBAL",
                published_at=_parse_iso(hit.get("created_at")),
                raw={"points": points, "comments": comments, "query": query},
            ))
    return signals


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


# ── First-party: Search Console rising queries ────────────────────────────────
def gsc_rising(db: Any, window: int = 14, min_impressions: int = 5) -> list[RawSignal]:
    """Queries the site already earns impressions for but ranks badly on.

    The strongest signal available, and the only one that is about *this*
    audience rather than the world's. A query with real impressions at position
    15 is demand already arriving at the door and bouncing — which is a better
    reason to write than anything trending globally.
    """
    cutoff = (_now() - timedelta(days=window)).date().isoformat()
    rows = (db.table("post_queries_daily")
            .select("query,impressions,clicks,position,slug")
            .gte("date", cutoff).limit(50000).execute().data or [])

    agg: dict[str, dict[str, float]] = {}
    for row in rows:
        query = (row.get("query") or "").strip()
        if not query:
            continue
        slot = agg.setdefault(query, {"impressions": 0.0, "clicks": 0.0, "pos_weight": 0.0})
        impressions = float(row.get("impressions") or 0)
        slot["impressions"] += impressions
        slot["clicks"] += float(row.get("clicks") or 0)
        slot["pos_weight"] += float(row.get("position") or 0) * impressions

    signals: list[RawSignal] = []
    for query, slot in agg.items():
        impressions = slot["impressions"]
        if impressions < min_impressions:
            continue
        position = slot["pos_weight"] / impressions if impressions else 0.0
        # Already ranking well means the demand is being served. Nothing to do.
        if position <= 5:
            continue
        signals.append(RawSignal(
            source="gsc_rising",
            platform="search_gap",
            title=query,
            url="",
            summary=(f"{int(impressions)} impressions at average position {position:.1f} "
                     f"with {int(slot['clicks'])} clicks — demand arriving but not converting."),
            engagement=impressions,
            geo="OWN",
            published_at=_now(),
            raw={"impressions": impressions, "position": round(position, 1),
                 "clicks": slot["clicks"]},
        ))
    return signals


# ── Paid provider hook ────────────────────────────────────────────────────────
def paid_trends_provider() -> list[RawSignal]:
    """Placeholder for a real interest-over-time source.

    Deliberately unimplemented rather than faked. `pytrends` cannot deliver this
    (429 on first call), and returning plausible-looking numbers from a stub
    would be worse than returning nothing: the learning layer cannot tell an
    invented trend from a measured one.

    To enable, set TRENDS_PROVIDER=serpapi|dataforseo plus its key, and implement
    the call here. The scout consumes RawSignal, so nothing downstream changes.
    """
    provider = os.environ.get("TRENDS_PROVIDER", "").strip().lower()
    if not provider:
        return []
    raise NotImplementedError(
        f"TRENDS_PROVIDER={provider!r} is set but no adapter is implemented. "
        "Add it in swarm/trends/sources.py:paid_trends_provider()."
    )
