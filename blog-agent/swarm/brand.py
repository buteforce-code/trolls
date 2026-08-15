"""
BrandProfile — the per-tenant template. One brand's identity, evidence and voice, in one
validated object that every agent and the GEO gate read from.

WHY THIS EXISTS
The swarm was written for exactly one brand. `Buteforce`, `Dhyaneshwaran`, `buteforce.com`
and seven hardcoded proof numbers appear 88 times across 17 files in `swarm/`, and
`brand_context.py` fell back to a literal `D:/Projects/...` path. One deployment was one
brand, permanently.

Worse than the hardcoding: the same facts were stated twice in incompatible forms. The proof
numbers lived in `config/positioning.md` as English (for the writer prompt) AND in `geo.py`
as regexes (for the gate). Two sources of truth for one set of facts is how the gate and the
prompt drift apart — and a drifted gate rejects correct posts.

So a profile is loaded once and derives BOTH halves:
  - the PROMPT half — English injected into the writer, ideator, linker, social agents
  - the GATE half   — regexes and name lists `geo.audit()` enforces

WHAT A PROFILE IS NOT
It is not settings. Every field here is a claim about a real company that a published,
competitor-naming, number-carrying blog post will assert in public on their domain. A wrong
`proof_point` is a fabricated statistic — the exact failure that put invented Unilever and
Nestlé statistics into production FAQPage schema on 2026-07-29. Hence `source` is mandatory
on every proof point and `validate()` refuses a profile that cannot satisfy its own gate.

STORAGE
JSON on disk today (`profiles/<slug>.json`), a `tenants.profile_json` column tomorrow. The
file format IS the column payload, so tenancy needs no conversion — only a different loader.

SELECTING A PROFILE
`BRAND_PROFILE=<slug>` env var, default `buteforce`. `PROFILES_DIR` overrides the directory.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_PROFILES_DIR = Path(__file__).resolve().parents[1] / "profiles"
DEFAULT_PROFILE_SLUG = "buteforce"


class ProfileError(ValueError):
    """A profile is missing, malformed, or cannot satisfy the gate it configures."""


# ── Puffery, shared by every brand ────────────────────────────────────────────────────────
# Adjectives that pretend to be evidence. Brand-independent: no company's real differentiator
# is the word "world-class". A profile may add to this list but cannot remove from it — the
# floor is the product, and a client talking us into "cutting-edge" is the thing being sold
# against. Deliberately excludes words with a legitimate technical sense in some domain
# ("seamless" seal, "robust" fixture); the writer prompt handles those.
UNIVERSAL_BANNED_ADJECTIVES: tuple[str, ...] = (
    "world-class", "cutting-edge", "cutting edge", "state-of-the-art", "best-in-class",
    "revolutionary", "revolutionis", "revolutioniz", "game-chang", "game chang",
    "transformative", "unparalleled", "groundbreaking", "industry-leading", "unmatched",
    "paradigm shift", "seismic shift", "tectonic shift", "supercharge", "turbocharge",
    "next-generation", "bleeding-edge",
)


@dataclass(frozen=True)
class ProofPoint:
    """One real, delivered, unrounded number this brand is allowed to claim.

    `label`   — how the writer is told to say it, e.g. "99.2% vision accuracy".
    `pattern` — how the gate recognises it in a draft. Inline flags allowed: `(?i)...`.
    `source`  — provenance. MANDATORY. "Ortho classifier, Mar 2026 acceptance run" is a
                source; "marketing" is not. Nothing without a traceable origin gets published
                as a statistic under a client's name.
    """

    label: str
    pattern: str
    source: str

    @property
    def regex(self) -> re.Pattern[str]:
        return _compile(self.pattern)

    def matches(self, text: str) -> bool:
        return bool(self.regex.search(text))


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise ProfileError(f"proof_point pattern is not a valid regex: {pattern!r} — {exc}") from exc


@dataclass(frozen=True)
class GateThresholds:
    """Per-brand gate strictness.

    Defaults are the Buteforce-tuned values the 25 GEO tests were written against. A brand
    with a thinner evidence base can be onboarded at lower thresholds — but `validate()`
    still refuses a profile that cannot meet its OWN numbers, so lowering these is an
    explicit, recorded decision rather than a silent degradation.
    """

    min_question_h2: int = 2
    answer_min_words: int = 40
    answer_max_words: int = 160
    min_proof_numbers: int = 2
    min_competitors_in_table: int = 2
    min_table_body_rows: int = 3
    not_a_fit_min_words: int = 40


@dataclass(frozen=True)
class BrandProfile:
    """Everything the swarm needs to write as one specific company."""

    # ── Identity ──────────────────────────────────────────────────────────────────────────
    slug: str
    name: str
    site_url: str
    internal_hosts: tuple[str, ...] = ()
    legal_name: str = ""
    tagline: str = ""

    # ── Entity / byline. A named person, never "the team" — SCAN 001's root cause was an
    #    entity gap, and one spelling everywhere or the knowledge graph sees two people. ────
    author_name: str = ""
    author_id: str = ""
    author_url: str = ""
    author_job_title: str = ""
    logo_url: str = ""
    # BCP-47 tag emitted as JSON-LD `inLanguage`. Neutral by default; a tenant writing for one
    # market sets its own ("en-IN", "en-GB"). Was hardcoded "en-IN" — wrong for anyone else.
    content_locale: str = "en"

    # ── Prompt-half text, injected verbatim into agents ───────────────────────────────────
    # Optional inline overrides. Left empty for brands whose long-form prose lives as
    # editable markdown in `config/<slug>/` — see `brand_context.py` for the precedence.
    # Prose belongs in markdown where a human will actually revise it; only the structured,
    # gate-critical facts have to be here.
    positioning: str = ""
    icp: str = ""
    voice_guardrails: str = ""
    do_not_name: tuple[str, ...] = ()

    # ── Gate-half evidence ────────────────────────────────────────────────────────────────
    proof_points: tuple[ProofPoint, ...] = ()
    # Every known rival, flattened. This is what the gate matches a draft's table against.
    # Derived from `competitors_by_cluster` when that is supplied — see `from_dict`.
    competitors: tuple[str, ...] = ()
    # Rivals grouped by the cluster taxonomy in `swarm/learning/scorer.py`. The writer is shown
    # only the group matching the post's own cluster: a document-AI post that gets handed
    # machine-vision vendors either writes a table about the wrong market or invents names, and
    # inventing names is the one thing the gate cannot forgive.
    competitors_by_cluster: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # canonical name → other spellings of the SAME vendor. Aliases let the gate recognise a
    # draft that wrote "AWS Textract" while still counting that vendor once.
    competitor_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    banned_adjectives_extra: tuple[str, ...] = ()

    thresholds: GateThresholds = field(default_factory=GateThresholds)

    # ── Derived views ─────────────────────────────────────────────────────────────────────
    @property
    def banned_adjectives(self) -> tuple[str, ...]:
        """Universal puffery plus this brand's own. Additive only — see the constant."""
        return UNIVERSAL_BANNED_ADJECTIVES + tuple(
            a for a in self.banned_adjectives_extra if a not in UNIVERSAL_BANNED_ADJECTIVES
        )

    @property
    def proof_labels(self) -> tuple[str, ...]:
        return tuple(p.label for p in self.proof_points)

    def found_proof_points(self, text: str) -> list[str]:
        """Labels of every proof point this text actually carries."""
        return [p.label for p in self.proof_points if p.matches(text)]

    # ── Competitors ───────────────────────────────────────────────────────────────────────
    def competitors_for(self, cluster: str | None = None) -> tuple[str, ...]:
        """The rivals a buyer for *this* cluster is really choosing between.

        Falls back to the full list when the cluster is unknown or has no group, so a new
        cluster degrades to "too many names" rather than to none — a writer given the wrong
        shortlist still writes a real table; a writer given nothing invents one.
        """
        if cluster:
            group = self.competitors_by_cluster.get(cluster)
            if group:
                return tuple(group)
        return self.competitors

    def competitor_shortlist(self, cluster: str | None = None, limit: int = 14) -> tuple[str, ...]:
        """Names to show a writer.

        With a cluster, the rivals for that market. Without one — the writer agent's system
        instruction is built once at startup, before any topic exists — a spread across every
        cluster rather than the head of the flat list, which is entirely machine-vision vendors
        and would aim every document-AI post at the wrong market.
        """
        if cluster:
            return self.competitors_for(cluster)[:limit]
        if not self.competitors_by_cluster:
            return self.competitors[:limit]

        groups = list(self.competitors_by_cluster.values())
        spread: dict[str, str] = {}
        depth = 0
        while len(spread) < limit and any(depth < len(g) for g in groups):
            for group in groups:
                if depth < len(group) and len(spread) < limit:
                    spread.setdefault(group[depth].lower(), group[depth])
            depth += 1
        return tuple(spread.values())

    def canonical_competitor(self, name: str) -> str:
        """The preferred spelling for a vendor, given any of its known aliases."""
        folded = name.strip().lower()
        for canonical, aliases in self.competitor_aliases.items():
            if folded == canonical.lower() or any(folded == a.lower() for a in aliases):
                return canonical
        return name

    def named_competitors(self, text: str) -> list[str]:
        """Distinct vendors this text actually names, canonicalised and case-folded.

        Counting distinct *vendors* rather than distinct matched strings is the point. The
        registry used to carry both "Omron" and "OMRON"; a table naming Omron once matched
        both and scored two competitors, passing a gate it should have failed.
        """
        haystack = text.lower()
        found: dict[str, str] = {}
        for name in self.competitors:
            spellings = (name, *self.competitor_aliases.get(name, ()))
            if any(s.lower() in haystack for s in spellings):
                canonical = self.canonical_competitor(name)
                found.setdefault(canonical.lower(), canonical)
        return sorted(found.values())

    @property
    def hosts(self) -> frozenset[str]:
        """Hosts that count as internal, so links to them are rewritten relative.

        Derived from `site_url` when not given explicitly, with the `www.` twin added — the
        original bug was `https://www.buteforce.com/services` costing a 308 on every crawl.
        """
        if self.internal_hosts:
            given = {h.lower().lstrip("/") for h in self.internal_hosts}
        else:
            given = {re.sub(r"^https?://", "", self.site_url).split("/")[0].lower()}
        twins = {h[4:] if h.startswith("www.") else f"www.{h}" for h in given}
        return frozenset(given | twins)

    # ── Validation ────────────────────────────────────────────────────────────────────────
    def validate(self) -> None:
        """Refuse a profile that cannot produce a post its own gate would pass.

        This is the intake's completion check. A tenant that has not supplied enough real
        evidence is not "configured with gaps" — it is unable to publish, and it should fail
        loudly at onboarding rather than at 3am inside a retry loop.
        """
        problems: list[str] = []

        # `positioning` is deliberately absent: it may legitimately live as markdown in
        # `config/<slug>/`. `brand_context` raises if no prose is found by any route.
        for name in ("slug", "name", "site_url", "author_name"):
            if not str(getattr(self, name)).strip():
                problems.append(f"`{name}` is required and empty.")

        if self.site_url and not self.site_url.startswith(("http://", "https://")):
            problems.append(f"`site_url` must be absolute, got {self.site_url!r}.")

        t = self.thresholds
        if len(self.proof_points) < t.min_proof_numbers:
            problems.append(
                f"{len(self.proof_points)} proof point(s) supplied but the gate demands "
                f"{t.min_proof_numbers} in every post. A post cannot pass. Collect more real "
                "numbers, or lower `thresholds.min_proof_numbers` as a recorded decision."
            )
        if len(self.competitors) < t.min_competitors_in_table:
            problems.append(
                f"{len(self.competitors)} competitor(s) supplied but every post must name "
                f"{t.min_competitors_in_table} in a comparison table. Name the real vendors "
                "this buyer is actually choosing between."
            )
        for p in self.proof_points:
            if not p.source.strip():
                problems.append(f"proof point {p.label!r} has no `source`. Provenance is mandatory.")
            p.regex  # compiles or raises ProfileError

        if t.answer_min_words >= t.answer_max_words:
            problems.append("`answer_min_words` must be below `answer_max_words`.")

        if problems:
            raise ProfileError(
                f"Brand profile {self.slug!r} is not publishable:\n  - "
                + "\n  - ".join(problems)
            )


# ── Loading ───────────────────────────────────────────────────────────────────────────────
def _profiles_dir() -> Path:
    return Path(os.environ.get("PROFILES_DIR", "").strip() or _PROFILES_DIR)


def from_dict(data: dict, *, slug: str = "") -> BrandProfile:
    """Build a profile from the JSON payload. Unknown keys are rejected, not ignored —
    a typo'd key would otherwise silently drop a client's real positioning."""
    # JSON has no comment syntax, and the competitor registry needs explaining to whoever
    # edits it next. Underscore-prefixed keys are documentation and never reach the profile.
    data = {k: v for k, v in data.items() if not k.startswith("_")}

    known = {f for f in BrandProfile.__dataclass_fields__}
    unknown = set(data) - known
    if unknown:
        raise ProfileError(
            f"Unknown key(s) in profile {slug or data.get('slug', '?')!r}: "
            f"{', '.join(sorted(unknown))}. Known keys: {', '.join(sorted(known))}."
        )

    raw_points = data.get("proof_points", ())
    try:
        points = tuple(ProofPoint(**p) for p in raw_points)
    except TypeError as exc:
        raise ProfileError(
            f"Each proof_point needs exactly `label`, `pattern`, `source` — {exc}"
        ) from exc

    thresholds = GateThresholds(**data.get("thresholds", {}))

    by_cluster = {
        cluster: tuple(names)
        for cluster, names in (data.get("competitors_by_cluster") or {}).items()
    }
    aliases = {
        canonical: tuple(spellings)
        for canonical, spellings in (data.get("competitor_aliases") or {}).items()
    }

    # The flat list the gate matches against is derived from the groups unless a profile
    # states it explicitly. Deriving it is what stops the two from drifting: a rival added to
    # a cluster for the writer would otherwise be a rival the gate still refuses to recognise.
    flat = tuple(data.get("competitors", ()))
    if not flat and by_cluster:
        seen: dict[str, str] = {}
        for names in by_cluster.values():
            for name in names:
                seen.setdefault(name.lower(), name)
        flat = tuple(seen.values())

    dicts = ("competitors_by_cluster", "competitor_aliases")
    tuples = ("internal_hosts", "do_not_name", "competitors", "banned_adjectives_extra")
    payload = {
        **{
            k: v for k, v in data.items()
            if k not in {"proof_points", "thresholds", *tuples, *dicts}
        },
        **{k: tuple(data.get(k, ())) for k in tuples if k != "competitors"},
        "competitors": flat,
        "competitors_by_cluster": by_cluster,
        "competitor_aliases": aliases,
        "proof_points": points,
        "thresholds": thresholds,
    }
    if slug:
        payload["slug"] = slug

    profile = BrandProfile(**payload)
    profile.validate()
    return profile


@lru_cache(maxsize=32)
def load(slug: str = "") -> BrandProfile:
    """Load and validate one profile by slug. Cached — profiles are immutable per process."""
    slug = slug or os.environ.get("BRAND_PROFILE", "").strip() or DEFAULT_PROFILE_SLUG
    path = _profiles_dir() / f"{slug}.json"
    if not path.exists():
        available = sorted(p.stem for p in _profiles_dir().glob("*.json"))
        raise ProfileError(
            f"No brand profile {slug!r} at {path}. Available: {', '.join(available) or 'none'}. "
            "Set BRAND_PROFILE to one of these, or add the profile."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProfileError(f"Profile {path} is not valid JSON: {exc}") from exc
    return from_dict(data, slug=slug)


def active() -> BrandProfile:
    """The profile this process is running as."""
    return load()
