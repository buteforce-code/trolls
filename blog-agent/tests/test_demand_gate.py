"""Demand gate tests.

The gate's whole value is that it refuses topics, so the tests that matter are
the ones that try to make it refuse the wrong thing — or, worse, quietly stop
refusing anything at all. A demand gate that has silently degraded into a
pass-through is indistinguishable from no gate, and that is the failure this
file exists to catch.

The anchor case is real: "AI precision agriculture India" was ideated, researched,
written to 2,517 words, cleared the GEO gate and the length gate, published on
2026-08-24, and earned zero impressions. It is pinned below as the topic this
gate must reject.

    python tests/test_demand_gate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm import demand  # noqa: E402
from swarm.demand import Measurement, Policy, PASS, REJECT, UNVERIFIED  # noqa: E402

POLICY = Policy(min_volume=50, on_unknown=REJECT, geo="IN", enabled=True)


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


class FakeProvider:
    """A provider whose answers the test dictates. `can_falsify` is settable
    because it is the flag the entire policy pivots on."""

    def __init__(self, measurement: Measurement, can_falsify: bool = True,
                 name: str = "fake", raises: Exception | None = None) -> None:
        self.name = name
        self.can_falsify = can_falsify
        self._m = measurement
        self._raises = raises
        self.calls = 0

    def lookup(self, keyword: str, geo: str) -> Measurement:
        self.calls += 1
        if self._raises:
            raise self._raises
        return self._m


# ── the anchor ────────────────────────────────────────────────────────────────
def test_the_zero_demand_post_is_rejected() -> int:
    """The regression anchor: a falsifiable provider reporting 0 must reject."""
    f = 0
    kw = "ai precision agriculture india"
    provider = FakeProvider(Measurement(kw, volume=0, found=True))
    v = demand.check(kw, provider, POLICY)
    if v.decision != REJECT:
        _fail(f"a 0-volume keyword must be rejected, got {v.decision!r}")
        f += 1
    if v.volume != 0:
        _fail(f"the measured volume must survive onto the verdict, got {v.volume!r}")
        f += 1
    if "0/mo" not in v.reason and "below" not in v.reason:
        _fail(f"the reason must state the measurement, got {v.reason!r}")
        f += 1
    return f


def test_a_real_keyword_passes() -> int:
    f = 0
    provider = FakeProvider(Measurement("computer vision quality control", volume=880, found=True))
    v = demand.check("Computer Vision Quality Control", provider, POLICY)
    if v.decision != PASS:
        _fail(f"880/mo must pass a 50/mo floor, got {v.decision!r}")
        f += 1
    if v.volume != 880:
        _fail("volume lost on the way to the verdict")
        f += 1
    return f


def test_volume_below_the_floor_is_rejected() -> int:
    f = 0
    provider = FakeProvider(Measurement("sarvam codex india", volume=49, found=True))
    v = demand.check("sarvam codex india", provider, POLICY)
    if v.decision != REJECT:
        _fail(f"49/mo must fail a 50/mo floor, got {v.decision!r}")
        f += 1
    return f


# ── the falsifiability split — the load-bearing rule ──────────────────────────
def test_unfalsifiable_provider_can_never_reject() -> int:
    """Search Console silence means 'no record', not 'no demand'.

    If this ever fails, the default configuration rejects every genuinely new
    topic and the queue dies quietly.
    """
    f = 0
    provider = FakeProvider(Measurement("brand new topic idea"),
                            can_falsify=False, name="gsc")
    v = demand.check("brand new topic idea", provider, POLICY)
    if v.decision == REJECT:
        _fail("an unfalsifiable provider must never produce a rejection")
        f += 1
    if v.decision != UNVERIFIED:
        _fail(f"expected UNVERIFIED from a provider with no record, got {v.decision!r}")
        f += 1
    return f


def test_unfalsifiable_low_volume_is_proven_demand_not_a_shortfall() -> int:
    """7 impressions in Search Console is proof of demand, not a measure of it.

    Comparing site impressions against a market-volume floor would reject exactly
    the first-party signals that produced both of this site's real wins.
    """
    f = 0
    provider = FakeProvider(Measurement("computer vision fmcg", volume=7, found=True),
                            can_falsify=False, name="gsc")
    v = demand.check("computer vision fmcg", provider, POLICY)
    if v.decision != PASS:
        _fail(f"a keyword GSC has actually seen must pass, got {v.decision!r}")
        f += 1
    if "proven" not in v.reason:
        _fail(f"the reason should distinguish proof from estimate, got {v.reason!r}")
        f += 1
    return f


def test_falsifiable_absence_is_a_rejection() -> int:
    f = 0
    provider = FakeProvider(Measurement("kw"), can_falsify=True, name="dataforseo")
    v = demand.check("some invented phrase", provider, POLICY)
    if v.decision != REJECT:
        _fail(f"a falsifiable provider finding nothing must reject, got {v.decision!r}")
        f += 1
    return f


# ── failure handling ──────────────────────────────────────────────────────────
def test_provider_error_never_reads_as_zero_demand() -> int:
    """The 2026-08-27 lesson: a transport failure is not a finding.

    An OpenRouter 402 was retried as if transient and cost eight topics. The same
    class of mistake here would be worse — it would look like the gate working.
    """
    f = 0
    provider = FakeProvider(Measurement("kw", error="HTTP 401 invalid credential"))
    v = demand.check("computer vision quality control", provider, POLICY)
    if v.volume is not None:
        _fail(f"an errored lookup must not report a volume, got {v.volume!r}")
        f += 1
    if "provider error" not in v.reason:
        _fail(f"the reason must name the error, got {v.reason!r}")
        f += 1
    return f


def test_on_unknown_is_configurable_both_ways() -> int:
    f = 0
    m = Measurement("kw", error="timeout")
    strict = demand.check("computer vision qc", FakeProvider(m),
                          Policy(min_volume=50, on_unknown=REJECT, geo="IN"))
    lenient = demand.check("computer vision qc", FakeProvider(m),
                           Policy(min_volume=50, on_unknown=UNVERIFIED, geo="IN"))
    if strict.decision != REJECT:
        _fail("DEMAND_ON_UNKNOWN=reject must reject on provider error")
        f += 1
    if lenient.decision != UNVERIFIED:
        _fail("DEMAND_ON_UNKNOWN=unverified must let the topic through")
        f += 1
    return f


def test_a_throwing_provider_cannot_fail_the_run() -> int:
    f = 0
    provider = FakeProvider(Measurement("kw"), raises=RuntimeError("connection reset"))
    try:
        v = demand.check("computer vision qc", provider, POLICY)
    except Exception as exc:
        _fail(f"check() must never raise, got {type(exc).__name__}: {exc}")
        return f + 1
    if v.decision != REJECT:
        _fail("a thrown provider should take the unknown path, not vanish")
        f += 1
    if "connection reset" not in v.reason:
        _fail("the underlying exception must survive into the reason")
        f += 1
    return f


# ── keyword hygiene ───────────────────────────────────────────────────────────
def test_malformed_keywords_are_rejected_without_a_lookup() -> int:
    """A defective keyword is a defect in the topic, and paying to confirm it is
    waste — a bad string returns a confident zero that reads like a finding."""
    f = 0
    for bad in ("", "   ", "ai", "computer"):
        provider = FakeProvider(Measurement("kw", volume=9999, found=True))
        v = demand.check(bad, provider, POLICY)
        if v.decision != REJECT:
            _fail(f"{bad!r} should be rejected as malformed, got {v.decision!r}")
            f += 1
        if provider.calls != 0:
            _fail(f"{bad!r} must not reach the provider — a paid lookup was wasted")
            f += 1
    return f


def test_a_sentence_is_not_a_keyword() -> int:
    f = 0
    long_kw = ("how do indian fmcg manufacturers choose between building and buying "
               "a computer vision quality control system in 2026")
    provider = FakeProvider(Measurement("kw", volume=500, found=True))
    v = demand.check(long_kw, provider, POLICY)
    if v.decision != REJECT:
        _fail(f"a 20-word sentence should be rejected, got {v.decision!r}")
        f += 1
    if provider.calls != 0:
        _fail("an over-long keyword must not reach the provider")
        f += 1
    return f


def test_normalisation_is_stable() -> int:
    f = 0
    cases = [
        ("Sarvam AI Coding Agent — India?", "sarvam ai coding agent india"),
        ("  computer   vision\nquality  control ", "computer vision quality control"),
        ("OCR vs. Document AI", "ocr vs document ai"),
        ("R&D automation", "r&d automation"),
    ]
    for raw, want in cases:
        got = demand.normalise_keyword(raw)
        if got != want:
            _fail(f"normalise({raw!r}) -> {got!r}, expected {want!r}")
            f += 1
    return f


# ── batch behaviour ───────────────────────────────────────────────────────────
def test_gate_topics_filters_and_annotates() -> int:
    f = 0
    topics = [
        {"title": "Good one", "target_keyword": "computer vision quality control"},
        {"title": "Bad one", "target_keyword": "ai precision agriculture india"},
    ]

    class PerKeyword:
        name, can_falsify = "fake", True

        def lookup(self, keyword: str, geo: str) -> Measurement:
            volume = 880 if "quality control" in keyword else 0
            return Measurement(keyword, volume=volume, found=True)

    kept, verdicts = demand.gate_topics(topics, PerKeyword(), POLICY)
    if len(kept) != 1 or kept[0]["title"] != "Good one":
        _fail(f"expected only the real keyword to survive, kept {[t['title'] for t in kept]}")
        f += 1
    if len(verdicts) != 2:
        _fail("every verdict must be returned, including rejections")
        f += 1
    if not kept or kept[0].get("demand", {}).get("volume") != 880:
        _fail("a surviving topic must carry its measurement forward for persistence")
        f += 1
    if topics[0].get("demand") is not None:
        _fail("gate_topics must not mutate the caller's topic dicts")
        f += 1
    return f


def test_switched_off_is_loud_not_silent() -> int:
    """DEMAND_PROVIDER=none must be visible in the verdict, not just absent."""
    f = 0
    off = Policy(min_volume=50, on_unknown=REJECT, geo="IN", enabled=False)
    v = demand.check("anything at all here", FakeProvider(Measurement("kw")), off)
    if v.decision != UNVERIFIED:
        _fail(f"a disabled gate must mark topics unverified, got {v.decision!r}")
        f += 1
    if v.provider != "none" or "switched off" not in v.reason:
        _fail("a disabled gate must say so on every verdict it issues")
        f += 1
    return f


def test_a_written_keyword_matches_a_typed_query() -> int:
    """The gap between how a keyword is written and how a query is typed.

    Live case: the gate returned `unverified` for "machine vision companies India" while
    the site was already earning impressions for "machine vision companies **in** india".
    One function word, and exact-plus-substring matching could not see across it — which
    made the free provider far weaker than the data it was reading.
    """
    from swarm.demand.providers import _content_tokens, _same_demand

    f = 0
    same = [
        ("machine vision companies india", "machine vision companies in india"),
        ("machine vision companies india", "top machine vision companies india"),
        ("computer vision quality control", "what is computer vision quality control"),
    ]
    for written, typed in same:
        if not _same_demand(_content_tokens(written), _content_tokens(typed)):
            _fail(f"{written!r} should match the typed query {typed!r}")
            f += 1

    # Containment, never mere overlap — these share two words and are different markets.
    different = [
        ("computer vision quality control", "computer vision fmcg"),
        ("document ai logistics", "document ai finance"),
        ("ai agents retail", "ai agents healthcare"),
    ]
    for a, b in different:
        if _same_demand(_content_tokens(a), _content_tokens(b)):
            _fail(f"{a!r} and {b!r} are different markets and must not collapse")
            f += 1
    return f


def test_summary_counts_every_outcome() -> int:
    f = 0
    verdicts = [
        demand.Verdict("a", PASS, 100, "fake", ""),
        demand.Verdict("b", REJECT, 0, "fake", ""),
        demand.Verdict("c", REJECT, 0, "fake", ""),
        demand.Verdict("d", UNVERIFIED, None, "fake", ""),
    ]
    line = demand.summarise(verdicts)
    for fragment in ("1 passed", "2 rejected", "1 unverified", "fake"):
        if fragment not in line:
            _fail(f"summary missing {fragment!r}: {line!r}")
            f += 1
    return f


def test_verdict_serialises_for_storage() -> int:
    f = 0
    v = demand.Verdict("computer vision fmcg", PASS, 500, "dataforseo", "clears floor",
                       {"location": "India"})
    blob = v.as_json()
    for key in ("keyword", "decision", "volume", "provider", "reason", "evidence"):
        if key not in blob:
            _fail(f"demand_json is missing {key!r} — the learning layer needs it")
            f += 1
    if blob["provider"] != "dataforseo":
        _fail("the provider must be stored per-row, not inferred from the environment later")
        f += 1
    return f


def main() -> int:
    tests = [
        ("the zero-demand post is rejected", test_the_zero_demand_post_is_rejected),
        ("a real keyword passes", test_a_real_keyword_passes),
        ("below the floor is rejected", test_volume_below_the_floor_is_rejected),
        ("unfalsifiable provider can never reject", test_unfalsifiable_provider_can_never_reject),
        ("GSC low volume is proof, not shortfall", test_unfalsifiable_low_volume_is_proven_demand_not_a_shortfall),
        ("falsifiable absence rejects", test_falsifiable_absence_is_a_rejection),
        ("provider error is not zero demand", test_provider_error_never_reads_as_zero_demand),
        ("on-unknown configurable both ways", test_on_unknown_is_configurable_both_ways),
        ("a throwing provider cannot fail the run", test_a_throwing_provider_cannot_fail_the_run),
        ("malformed keywords cost no lookup", test_malformed_keywords_are_rejected_without_a_lookup),
        ("a sentence is not a keyword", test_a_sentence_is_not_a_keyword),
        ("normalisation is stable", test_normalisation_is_stable),
        ("gate_topics filters and annotates", test_gate_topics_filters_and_annotates),
        ("switched off is loud", test_switched_off_is_loud_not_silent),
        ("written keyword matches typed query", test_a_written_keyword_matches_a_typed_query),
        ("summary counts every outcome", test_summary_counts_every_outcome),
        ("verdict serialises for storage", test_verdict_serialises_for_storage),
    ]
    total = 0
    for name, fn in tests:
        failures = fn()
        total += failures
        print(f"{'PASS' if failures == 0 else 'FAIL'}  {name}")
    print(f"\n{'ALL TESTS PASSED' if total == 0 else f'{total} FAILURE(S)'}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
