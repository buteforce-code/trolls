"""Content format classification.

The missing dimension. The bandit currently learns over (cluster x source) — what
a post is about and where the idea came from — but not *how it is written*. A
case study and a listicle on the same subject are different products and can
perform very differently.

Why this file exists now rather than when the bandit can use it: format is only
learnable once it has been recorded, and it can only be recorded going forward.
Waiting until there are enough posts to split arms by format would mean starting
the clock at that point and waiting again. Classifying from today — and
backfilling what already exists — means the data is ready when the sample size
is.

Why the bandit does not use it yet: 10 matured posts across ~6 arms already
leaves most arms with one or two observations. Splitting again by format would
put nearly every cell below one observation, and a posterior fitted to that is
just the prior wearing a disguise. `LEARN_FORMAT_ARMS` turns it on; the honest
threshold is somewhere around 40-50 matured posts.

Classification is structural, not semantic: it reads the shape of the draft —
heading patterns, list density, numeric headings, question headings — rather
than asking a model. Deterministic, free, reproducible, and it cannot drift
between runs the way a prompt-based classifier would.
"""
from __future__ import annotations

import os
import re
from typing import Any

# The formats worth telling apart. Deliberately few: each one has to earn enough
# posts to be learnable, and a taxonomy of fifteen would never fill.
FORMATS = ("listicle", "case_study", "guide", "comparison", "explainer", "news")
DEFAULT_FORMAT = "explainer"

FORMAT_ARMS = os.environ.get("LEARN_FORMAT_ARMS", "false").strip().lower() == "true"

_NUMBERED_HEADING = re.compile(r"^#{2,3}\s*\d+[\.\)]?\s+", re.M)
_QUESTION_HEADING = re.compile(r"^#{2,3}\s+.*\?\s*$", re.M)
_HEADING = re.compile(r"^#{2,3}\s+(.+)$", re.M)
_LIST_ITEM = re.compile(r"^\s*[-*+]\s+|^\s*\d+\.\s+", re.M)

_CASE_STUDY_CUES = ("case study", "we deployed", "the problem", "what broke",
                    "before and after", "full case study", "how we built")
_COMPARISON_CUES = (" vs ", " vs. ", "versus", "which is right", "compared",
                    "alternative", "build vs buy")
_GUIDE_CUES = ("how to", "step by step", "step-by-step",
               "getting started", "checklist", "playbook")

# "guide", "handbook" and friends as whole words, so "The Complete 2026 Guide"
# is caught. A fixed "complete guide" substring misses it — the year sits in the
# middle, and titles routinely put something there.
_GUIDE_RE = re.compile(r"\b(guide|handbook|walkthrough|tutorial)\b")
_NEWS_CUES = ("announced", "launched", "this week", "just released", "rival",
              "unveiled", "acquires", "raises")


def classify(title: str, body: str = "", tags: list[str] | None = None) -> str:
    """Best-guess format from a post's title and structure.

    Order matters: the tests are checked most-specific first, because a case
    study usually also contains a numbered list and a comparison usually also
    reads like a guide. Whichever test is most distinctive should win.
    """
    text = f"{title} {' '.join(tags or [])}".lower()
    body_lower = (body or "").lower()
    combined = f"{text} {body_lower[:4000]}"

    # Explicit "N things" in the title is the strongest single tell.
    if re.match(r"^\s*\d+\s+\w", title.strip()) or re.search(r"\b\d+\s+(ways|things|reasons|tips|examples|mistakes|questions)\b", text):
        return "listicle"

    if any(cue in text for cue in _COMPARISON_CUES):
        return "comparison"

    if any(cue in combined for cue in _CASE_STUDY_CUES):
        return "case_study"

    if any(cue in text for cue in _NEWS_CUES):
        return "news"

    if any(cue in text for cue in _GUIDE_CUES) or _GUIDE_RE.search(text):
        return "guide"

    if not body:
        return DEFAULT_FORMAT

    headings = _HEADING.findall(body)
    numbered = len(_NUMBERED_HEADING.findall(body))
    questions = len(_QUESTION_HEADING.findall(body))
    list_items = len(_LIST_ITEM.findall(body))
    words = max(1, len(body.split()))

    # A majority of numbered headings is a listicle whatever the title claims.
    if headings and numbered / len(headings) > 0.5:
        return "listicle"
    # Mostly question headings reads as an FAQ-shaped explainer.
    if headings and questions / len(headings) > 0.4:
        return "explainer"
    # Dense bullets over many sections is guide-shaped.
    if len(headings) >= 5 and (list_items / words) > 0.02:
        return "guide"

    return DEFAULT_FORMAT


def backfill(db: Any, dry_run: bool = False) -> list[str]:
    """Classify every topic that has no format recorded yet.

    Idempotent — only fills nulls, so a manual correction is never overwritten.
    """
    log: list[str] = []
    topics = (db.table("topics").select("id,slug,title,tags,content_format")
              .limit(5000).execute().data or [])
    todo = [t for t in topics if not t.get("content_format")]
    log.append(f"[formats] {len(topics)} topics, {len(todo)} unclassified")
    if not todo:
        return log

    posts = (db.table("blog_posts").select("topic_id,mdx_final,mdx_draft")
             .limit(5000).execute().data or [])
    body_by_topic = {
        p["topic_id"]: (p.get("mdx_final") or p.get("mdx_draft") or "")
        for p in posts
    }

    counts: dict[str, int] = {}
    for topic in todo:
        fmt = classify(
            topic.get("title") or "",
            body_by_topic.get(topic["id"], ""),
            topic.get("tags"),
        )
        counts[fmt] = counts.get(fmt, 0) + 1
        if not dry_run:
            db.table("topics").update({"content_format": fmt}).eq("id", topic["id"]).execute()

    log.append("  " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if dry_run:
        log.append("  dry run — nothing written")
    return log
