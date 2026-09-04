"""The demand gate — the check that was missing from every other gate.

Why this exists
---------------
Every gate in this pipeline verifies *craft*. `length_gate` enforces a word
floor. `geo.py` enforces question H2s, unrounded proof numbers, a competitor
table and a "not a fit if" section. `auditor.py` checks the facts are sourced
and the angle is non-obvious. All of them are real and all of them work.

Not one of them ever asked whether a human being types the phrase the post is
written to rank for.

Measured 2026-09-03 across 38 published posts and 112 days: 1,899 impressions,
17 clicks, and 92.7% of those impressions belong to two posts. The keywords the
ideator invented for the rest — "AI precision agriculture India" (0 impressions),
"AI web applications healthcare India" (0), "custom AI booking systems Indian
SMBs" (1), "AI workflow automation real estate India" (3) — did not rank badly.
They have no demand behind them at all. A well-formed 2,500-word post aimed at a
phrase nobody searches is a perfect artefact of a broken aim, and the pipeline
had no way to notice.

So: one gate, at the only chokepoint every topic passes through, that asks the
one question the others do not.

Falsifiable vs unfalsifiable providers
--------------------------------------
The distinction that makes this module work, and the reason it is not just a
volume lookup.

  * A **falsifiable** provider (DataForSEO, Google Ads) can prove *absence* of
    demand. "This phrase gets 0 searches a month" is a real finding, and a
    topic that earns it is rejected outright.

  * An **unfalsifiable** provider (Search Console) cannot. It only knows queries
    this site already appears for, so silence means "never seen", not "nobody
    searches it". Treating its silence as a rejection would reject every genuinely
    new topic and halt the queue — the gate would look like it was working right
    up until it had produced nothing for a week.

A provider therefore declares which kind it is, and the policy below reads that
declaration rather than guessing. Search Console still earns its place: a keyword
it *has* seen is demand proven by this audience rather than estimated by a third
party, which is the strongest signal available anywhere in this system. It
promotes; it does not veto.

That split is what makes `DEMAND_PROVIDER` a switch you can actually throw. Start
free on `gsc` and the gate promotes proven keywords while passing the unknown
ones through, flagged. Move to `dataforseo` and the same gate starts vetoing.
Nothing else in the pipeline changes, and no topic is scored under two different
definitions of "checked" — every verdict records which provider answered.

Import-clean on purpose: no supabase, no requests, no ADK. The policy is the part
worth testing hardest, so it is testable without a network or a database.

    python tests/test_demand_gate.py
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

# ── decisions ─────────────────────────────────────────────────────────────────
# Three, not two. "Rejected because the provider proved there is no demand" and
# "not verified because nobody could tell us" are different facts about a topic,
# and collapsing them would make the gate's own reliability invisible: a week of
# provider outages would read exactly like a week of good filtering.
PASS = "pass"
REJECT = "reject"
UNVERIFIED = "unverified"

# What `DEMAND_ON_UNKNOWN` may be set to when a falsifiable provider fails to
# answer. Default is REJECT, deliberately — see `_policy()`.
UNKNOWN_ACTIONS = (REJECT, UNVERIFIED)

DEFAULT_MIN_VOLUME = 50
DEFAULT_GEO = "IN"


@dataclass(frozen=True)
class Measurement:
    """What a provider found. Purely a report — it carries no decision.

    `found=False` with `error=None` means the provider looked and the keyword is
    not there. For a falsifiable provider that is evidence of zero demand; for an
    unfalsifiable one it means nothing at all. The policy, not the provider,
    knows which reading applies.
    """
    keyword: str
    volume: int | None = None
    found: bool = False
    error: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Verdict:
    """The gate's decision, and enough of its reasoning to argue with.

    Persisted to `topics.demand_json`, so a post's outcome can later be scored
    against the demand that was measured *before* it was written rather than the
    demand inferred after it flopped.
    """
    keyword: str
    decision: str
    volume: int | None
    provider: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return self.decision == REJECT

    def as_json(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "decision": self.decision,
            "volume": self.volume,
            "provider": self.provider,
            "reason": self.reason,
            "evidence": self.evidence,
        }

    def line(self) -> str:
        """One log line, in the shape the other gates print."""
        vol = "—" if self.volume is None else f"{self.volume}/mo"
        return f"[demand] {self.decision.upper():10s} {vol:>10s}  {self.keyword!r} — {self.reason}"


class DemandProvider(Protocol):
    """What the gate needs from a source of demand data.

    `can_falsify` is the load-bearing member. A provider that cannot prove
    absence must never be allowed to veto, no matter how it is configured.
    """
    name: str
    can_falsify: bool

    def lookup(self, keyword: str, geo: str) -> Measurement: ...


# ── keyword hygiene ───────────────────────────────────────────────────────────
# Checked before any lookup, because a malformed keyword wastes a paid API call
# and, worse, returns a confident zero that reads like a real finding.
_MAX_KEYWORD_WORDS = 10
_MAX_KEYWORD_CHARS = 80


def normalise_keyword(raw: Any) -> str:
    """Lowercase, collapse whitespace, strip the punctuation providers choke on.

    Google's keyword endpoints match on a normalised form; sending "Sarvam AI
    Coding Agent — India?" and sending "sarvam ai coding agent india" are the
    same query to them but different cache keys to us, which would fragment the
    evidence for one keyword across several rows.
    """
    text = re.sub(r"[^\w\s&+-]", " ", str(raw or "")).strip().lower()
    return re.sub(r"\s+", " ", text)


def keyword_defect(keyword: str) -> str | None:
    """Why this string cannot be a target keyword, or None if it can.

    Deliberately narrow. The gate's job is demand, not editorial judgement — the
    only defects caught here are the ones that make a *lookup* meaningless.
    """
    if not keyword:
        return "empty target keyword"
    words = keyword.split()
    if len(words) < 2:
        return f"single-word keyword {keyword!r} — too broad to rank or to measure"
    if len(words) > _MAX_KEYWORD_WORDS:
        return f"{len(words)} words — a sentence, not a keyword"
    if len(keyword) > _MAX_KEYWORD_CHARS:
        return f"{len(keyword)} characters — exceeds the {_MAX_KEYWORD_CHARS}-char lookup limit"
    return None


# ── policy ────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Policy:
    min_volume: int = DEFAULT_MIN_VOLUME
    on_unknown: str = REJECT
    geo: str = DEFAULT_GEO
    enabled: bool = True


def _policy() -> Policy:
    """Resolve the gate's policy from the environment.

    `DEMAND_ON_UNKNOWN` defaults to `reject`, and that is the deliberate choice.
    The two failure modes are not symmetric: a stalled queue is loud — it shows
    on the dashboard, and the liveness alarm pages on it — while a published post
    aimed at nothing is completely silent and costs a slot of a new domain's
    reputation that cannot be refunded. Given a provider that normally works and
    momentarily does not, waiting is the cheaper mistake.

    It stays configurable because that reasoning inverts the moment demand data
    becomes hard to get, and an operator who needs to ship should not have to
    edit this file to do it.
    """
    return Policy(
        min_volume=_env_int("DEMAND_MIN_VOLUME", DEFAULT_MIN_VOLUME),
        on_unknown=_env_choice("DEMAND_ON_UNKNOWN", UNKNOWN_ACTIONS, REJECT),
        geo=(os.environ.get("DEMAND_GEO", DEFAULT_GEO).strip().upper() or DEFAULT_GEO),
        enabled=os.environ.get("DEMAND_PROVIDER", "gsc").strip().lower() != "none",
    )


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)).strip())
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


def _env_choice(name: str, allowed: tuple[str, ...], default: str) -> str:
    value = os.environ.get(name, default).strip().lower()
    return value if value in allowed else default


def judge(measurement: Measurement, provider_name: str, can_falsify: bool,
          policy: Policy | None = None) -> Verdict:
    """Turn one provider's report into a decision. The whole policy, in one place.

    Separated from the lookup so it can be tested exhaustively without a network,
    and so a second provider cannot quietly arrive with a second set of rules.
    """
    pol = policy or _policy()
    kw = measurement.keyword

    if measurement.error:
        # The provider broke. This is never evidence about the keyword, so a
        # falsifiable provider does not get to reject on it — the policy does.
        decision = pol.on_unknown
        return Verdict(kw, decision, None, provider_name,
                       f"provider error, {decision} per DEMAND_ON_UNKNOWN: {measurement.error}",
                       dict(measurement.evidence))

    if not measurement.found:
        if not can_falsify:
            # Silence from an unfalsifiable provider is an absence of evidence,
            # not evidence of absence. Pass it through, but never as a clean pass.
            return Verdict(kw, UNVERIFIED, None, provider_name,
                           f"{provider_name} has no record of this keyword and cannot "
                           "prove absence of demand — unverified, not cleared",
                           dict(measurement.evidence))
        return Verdict(kw, REJECT, 0, provider_name,
                       f"no measurable search demand (floor {pol.min_volume}/mo)",
                       dict(measurement.evidence))

    volume = measurement.volume
    if volume is None:
        return Verdict(kw, UNVERIFIED, None, provider_name,
                       f"{provider_name} matched the keyword but returned no volume",
                       dict(measurement.evidence))

    if volume < pol.min_volume:
        if not can_falsify:
            # A low count from Search Console is this site's impressions, not the
            # world's search volume. It is proof of demand, not a measure of it.
            return Verdict(kw, PASS, volume, provider_name,
                           f"proven demand — this site already earns impressions for it",
                           dict(measurement.evidence))
        return Verdict(kw, REJECT, volume, provider_name,
                       f"{volume}/mo is below the {pol.min_volume}/mo floor",
                       dict(measurement.evidence))

    return Verdict(kw, PASS, volume, provider_name,
                   f"{volume}/mo clears the {pol.min_volume}/mo floor",
                   dict(measurement.evidence))


def check(keyword: Any, provider: DemandProvider | None = None,
          policy: Policy | None = None) -> Verdict:
    """Evaluate one keyword end to end. The function the pipeline calls.

    Never raises. A gate that can crash the run it is protecting has made the
    pipeline less reliable than it was without one, which is the opposite of the
    point — so a provider that throws is folded into the same unknown path as a
    provider that returns an error.
    """
    pol = policy or _policy()
    kw = normalise_keyword(keyword)

    if not pol.enabled:
        return Verdict(kw, UNVERIFIED, None, "none",
                       "DEMAND_PROVIDER=none — the demand gate is switched off", {})

    defect = keyword_defect(kw)
    if defect:
        # A malformed keyword is rejected regardless of provider: it is a defect
        # in the topic, not a finding about the market, and no lookup can fix it.
        return Verdict(kw, REJECT, None, "gate", defect, {"defect": defect})

    if provider is None:
        from swarm.demand.providers import resolve_provider

        provider = resolve_provider()

    try:
        measurement = provider.lookup(kw, pol.geo)
    except Exception as exc:  # a provider must not be able to fail the run
        measurement = Measurement(kw, error=f"{type(exc).__name__}: {exc}"[:300])

    return judge(measurement, provider.name, provider.can_falsify, pol)


def gate_topics(topics: list[dict], provider: DemandProvider | None = None,
                policy: Policy | None = None,
                log: list[str] | None = None) -> tuple[list[dict], list[Verdict]]:
    """Filter a batch of ideated topics. Returns (survivors, every verdict).

    Every verdict is returned, not only the rejections. The ones that were thrown
    away are the most valuable rows this system produces — they are the record of
    what the gate is actually saving, and the number the dashboard should show a
    prospective buyer.

    A surviving topic carries its verdict in `demand`, so the caller persists the
    measurement alongside the topic rather than measuring twice.
    """
    if provider is None and (policy or _policy()).enabled:
        from swarm.demand.providers import resolve_provider

        provider = resolve_provider()

    survivors: list[dict] = []
    verdicts: list[Verdict] = []
    for topic in topics:
        verdict = check(topic.get("target_keyword"), provider, policy)
        verdicts.append(verdict)
        if log is not None:
            log.append("  " + verdict.line())
        if verdict.blocked:
            continue
        survivor = dict(topic)
        survivor["demand"] = verdict.as_json()
        survivors.append(survivor)
    return survivors, verdicts


def summarise(verdicts: list[Verdict]) -> str:
    """One line for the tick log and the dashboard strip."""
    if not verdicts:
        return "[demand] nothing to check"
    counts = {PASS: 0, REJECT: 0, UNVERIFIED: 0}
    for v in verdicts:
        counts[v.decision] = counts.get(v.decision, 0) + 1
    provider = verdicts[0].provider
    return (f"[demand] {counts[PASS]} passed, {counts[REJECT]} rejected, "
            f"{counts[UNVERIFIED]} unverified — provider {provider}")
