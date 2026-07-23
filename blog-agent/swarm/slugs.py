"""Canonical slug generation for blog topics.

Single source of truth. Previously `_slugify` was copy-pasted into
`autopilot.py`, `run.py` and `seed_topics.py`, all ending in `slug[:60]` — a
blind character cut that shipped seven live URLs severed mid-word
(`...mean-for-manuf`, `...what-unileve`, `...what-is-the-glassw`).

Rules, in order:
  1. Normalise to lowercase ASCII words joined by hyphens.
  2. If it fits, keep it — a readable question-intent slug like
     `how-much-does-a-computer-vision-qc-system-cost` outranks a terser one.
  3. Only when over-length, drop filler words (keeping keyword-bearing ones).
  4. Only if still over-length, truncate on a word boundary — never inside one.
  5. Never end on a filler word.
"""
from __future__ import annotations

import re

MAX_SLUG_LEN = 60

# Dropped only when a slug is over-length, so short titles keep their natural
# phrasing. Question words (how/what/why) are deliberately absent — they carry
# search intent and belong in the URL when the title is a question.
FILLER_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "of", "for", "to", "in", "on", "at",
    "by", "with", "from", "into", "onto", "as", "is", "are", "was", "were",
    "be", "been", "that", "this", "these", "those", "it", "its", "your",
    "our", "we", "you", "they", "them", "here", "there", "about", "over",
})

# A slug may never end on one of these — `...partners-in-india-an` reads broken.
# Question words are safe to lead with but read as orphaned when trailing, so
# they are stripped here only ("...need-local-ai-partners-india-what").
TRAILING_FILLER = FILLER_WORDS | {
    "vs", "via", "per", "what", "whats", "which", "how", "why", "who", "when",
    "where", "does", "do", "did", "youre", "thats", "actually",
}


def _words(text: str) -> list[str]:
    """Lowercase the text and split it into clean alphanumeric word tokens."""
    lowered = text.lower()
    # Possessives collapse rather than leaving a stray "s": "India's" -> "indias".
    lowered = re.sub(r"['’]s\b", "s", lowered)
    lowered = re.sub(r"['’]", "", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return lowered.split()


def _trim_trailing_filler(words: list[str]) -> list[str]:
    while len(words) > 1 and words[-1] in TRAILING_FILLER:
        words = words[:-1]
    return words


def _fit(words: list[str], max_len: int) -> list[str]:
    """Take whole words while the joined slug stays within `max_len`."""
    kept: list[str] = []
    length = 0
    for word in words:
        added = len(word) if not kept else len(word) + 1  # +1 for the hyphen
        if length + added > max_len:
            break
        kept.append(word)
        length += added
    return kept


def slugify(text: str, max_len: int = MAX_SLUG_LEN) -> str:
    """Return a URL-safe slug that never cuts a word in half.

    >>> slugify("The SITAC Effect: What India's New AI Corridors Mean for Manufacturing Startups")
    'sitac-effect-indias-new-ai-corridors-mean-manufacturing-startups'
    """
    words = _words(text)
    if not words:
        return ""

    # 2. Fits as-is — keep the natural, readable phrasing.
    if len("-".join(words)) <= max_len:
        return "-".join(_trim_trailing_filler(words))

    # 3. Over-length: drop filler, keeping the keyword-bearing words.
    condensed = [w for w in words if w not in FILLER_WORDS] or words
    if len("-".join(condensed)) <= max_len:
        return "-".join(_trim_trailing_filler(condensed))

    # 4. Still too long: truncate on a word boundary.
    return "-".join(_trim_trailing_filler(_fit(condensed, max_len)))
