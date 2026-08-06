"""Map analytics URLs back to post slugs.

Search Console reports full URLs, GA4 reports paths, and the pipeline thinks in
slugs. Everything downstream keys on slug, so this is the join that makes the
whole feedback loop line up.

Two resolution strategies, in order:

  1. `blog_posts.published_url` — the URL the publisher actually wrote. Exact,
     and survives any future change to the blog's URL shape.
  2. `/blog/<slug>` pattern     — covers posts published before a URL was
     recorded, and any host/protocol variant GSC reports.

Anything that resolves to neither (homepage, /services, tag pages) returns None
and is skipped rather than guessed at. A mis-attributed pageview is worse than a
missing one: it silently credits the wrong post in the learning loop.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urlsplit

# Must stay in step with swarm/slugs.py, which decides what a slug may contain.
BLOG_PATH_RE = re.compile(r"^/blog/([a-z0-9][a-z0-9-]{0,79})$")


def normalise_path(url_or_path: str) -> str:
    """Reduce any URL or path to a bare, comparable path.

    Drops scheme, host, query and fragment; decodes percent-escapes; strips the
    trailing slash. GSC and GA4 disagree on nearly all of these, and the same
    page arrives in several shapes across a single report.
    """
    if not url_or_path:
        return ""
    raw = str(url_or_path).strip()
    parts = urlsplit(raw if "//" in raw else f"//{raw}" if raw.startswith("www.") else raw)
    path = unquote(parts.path or "")
    if not path.startswith("/"):
        path = f"/{path}"
    if len(path) > 1:
        path = path.rstrip("/")
    return path.lower()


def slug_from_path(path: str) -> str | None:
    """Slug implied by a `/blog/<slug>` path, else None."""
    match = BLOG_PATH_RE.match(normalise_path(path))
    return match.group(1) if match else None


def build_index(db: Any) -> dict[str, str]:
    """{normalised path -> slug} for every post that has been published.

    Built from the recorded `published_url` first; the path pattern then fills in
    anything that URL did not cover.
    """
    index: dict[str, str] = {}

    topics = db.table("topics").select("id,slug").limit(5000).execute().data or []
    slug_by_id = {t["id"]: t["slug"] for t in topics}

    posts = (db.table("blog_posts").select("topic_id,published_url")
             .not_.is_("published_url", "null").limit(5000).execute().data or [])
    for post in posts:
        slug = slug_by_id.get(post.get("topic_id"))
        if not slug:
            continue
        path = normalise_path(post.get("published_url") or "")
        if path and path != "/":
            index[path] = slug

    # Canonical shape for every known slug, so a post whose published_url was
    # never recorded still resolves.
    for slug in slug_by_id.values():
        index.setdefault(f"/blog/{slug}", slug)

    return index


def resolve(url_or_path: str, index: dict[str, str]) -> str | None:
    """Slug for one analytics row, or None when the row is not a blog post."""
    path = normalise_path(url_or_path)
    if not path:
        return None
    hit = index.get(path)
    if hit:
        return hit
    return slug_from_path(path)
