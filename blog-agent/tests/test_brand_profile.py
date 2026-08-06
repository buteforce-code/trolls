"""BrandProfile tests — the template layer, and the gate running for a brand that is not us.

WHY THIS FILE EXISTS
`GO-TO-MARKET.md` Stage 2 listed "the GEO gate has never run for a non-Buteforce brand" as a
blocker, and it was accurate: every proof number, competitor and byline the gate enforced was
ours, so "it generalises" was an untested assumption sitting under the only differentiator.

The sharp test here is `test_a_post_written_for_us_fails_another_brands_gate`. A gate that
passes everyone's content is not a gate. If ACME's profile accepted a post carrying Buteforce's
99.2% and naming Buteforce's competitors, the whole per-tenant evidence model would be theatre.

Same harness as the other suites: a plain script, no pytest, `swarm/geo.py` import-clean.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm import brand, geo  # noqa: E402
from swarm.brand import ProfileError  # noqa: E402


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


def _words(n: int) -> str:
    return " ".join(["throughput"] * n)


# ── A second, deliberately unrelated brand ────────────────────────────────────────────────
# Fictional. A dental-practice scheduling SaaS shares nothing with an industrial AI shop — no
# vertical, no vocabulary, no rival, no number — so any Buteforce assumption still baked into
# the gate shows up immediately rather than passing by coincidence.
ACME = brand.from_dict(
    {
        "slug": "acme-dental",
        "name": "Chairside",
        "site_url": "https://chairside.example",
        "author_name": "Priya Raghunathan",
        "author_job_title": "Clinical Operations Lead",
        "proof_points": [
            {
                "label": "31% fewer no-shows",
                "pattern": r"\b31\s*%",
                "source": "Rollout review, 14 practices, Q1 2026",
            },
            {
                "label": "4.2 minutes saved per booking",
                "pattern": r"(?i)\b4\.2\s*(?:min(?:ute)?s?)\b",
                "source": "Time-and-motion study, Chennai pilot clinic",
            },
            {
                "label": "18-day onboarding",
                "pattern": r"(?i)\b18[-\s]day\b",
                "source": "Median across 14 practices, Q1 2026",
            },
        ],
        "competitors": ["Dentrix", "Curve Dental", "Open Dental", "Praktika"],
    }
)


def _acme_post() -> str:
    """A compliant post for Chairside: their numbers, their rivals, their disqualification."""
    return (
        '---\ntitle: "Scheduling"\ndescription: "Meta."\ndate: "2026-08-04"\n'
        'author: "Priya Raghunathan"\ndateModified: "2026-08-04"\n---\n\n'
        "## What does practice scheduling software actually reduce?\n\n"
        "Practice scheduling software reduces the two costs that dominate a small dental "
        "clinic's front desk: unfilled chair time and manual rebooking. Across fourteen "
        "practices running Chairside through Q1 2026 the measured result was 31% fewer "
        "no-shows and 4.2 minutes saved per booking, because confirmation and waitlist "
        "backfill stop being a receptionist's phone task. Neither number depends on the "
        "clinic changing its clinical workflow, which is why the effect shows up in the "
        "first month rather than after a staffing change or a new hire settles in.\n\n"
        "## How long does it take to switch systems?\n\n"
        "Switching took a median of 18-day onboarding across those same fourteen practices, "
        "measured from contract signature to the first week run entirely on the new "
        "schedule. Most of that window is chart and recall-list migration rather than "
        "training, so a practice with clean data in its previous system finishes sooner "
        "and one carrying a decade of paper recall cards takes materially longer than the "
        "median suggests.\n\n"
        "| Option | Best for | Where it wins over Chairside |\n"
        "|---|---|---|\n"
        "| Dentrix | Large multi-site groups | Deepest imaging and claims integration |\n"
        "| Curve Dental | Cloud-first practices | Longer track record, bigger support org |\n"
        "| Open Dental | Technical practices | Open source, no per-chair licence at all |\n\n"
        "## Not a fit if\n\n" + _words(50) + "\n"
    )


# ── Profile validation ────────────────────────────────────────────────────────────────────
def test_the_real_profile_loads_and_validates() -> int:
    try:
        p = brand.load("buteforce")
    except ProfileError as exc:
        _fail(f"the shipped Buteforce profile does not validate: {exc}")
        return 1
    failures = 0
    if p.author_name != "Dhyaneshwaran":
        _fail(f"author_name is {p.author_name!r} — must match the live site's rendered byline")
        failures += 1
    if len(p.proof_points) != 7:
        _fail(f"expected the 7 documented proof points, got {len(p.proof_points)}")
        failures += 1
    if "buteforce.com" not in p.hosts or "www.buteforce.com" not in p.hosts:
        _fail(f"both host spellings must be internal, got {sorted(p.hosts)}")
        failures += 1
    return failures


def test_a_profile_that_cannot_pass_its_own_gate_is_refused() -> int:
    """The intake's completion check: too little evidence must fail at onboarding, loudly."""
    try:
        brand.from_dict(
            {
                "slug": "thin",
                "name": "Thin Co",
                "site_url": "https://thin.example",
                "author_name": "A Person",
                "proof_points": [
                    {"label": "one", "pattern": r"\b1\b", "source": "somewhere"},
                ],
                "competitors": ["OnlyRival"],
            }
        )
    except ProfileError as exc:
        msg = str(exc)
        failures = 0
        if "proof point" not in msg:
            _fail("the error must name the missing proof points")
            failures += 1
        if "competitor" not in msg:
            _fail("the error must name the missing competitors")
            failures += 1
        return failures
    _fail("a profile with 1 proof point and 1 competitor was accepted; no post could ever pass")
    return 1


def test_a_proof_point_without_provenance_is_refused() -> int:
    """A number with no source is how invented statistics reach production."""
    try:
        brand.from_dict(
            {
                "slug": "unsourced",
                "name": "Unsourced Co",
                "site_url": "https://unsourced.example",
                "author_name": "A Person",
                "proof_points": [
                    {"label": "99% good", "pattern": r"\b99\s*%", "source": "  "},
                    {"label": "50% faster", "pattern": r"\b50\s*%", "source": "a real study"},
                ],
                "competitors": ["One", "Two"],
            }
        )
    except ProfileError as exc:
        if "source" not in str(exc):
            _fail(f"error should name the missing source, got: {exc}")
            return 1
        return 0
    _fail("a proof point with a blank source was accepted")
    return 1


def test_an_unknown_key_is_refused_not_ignored() -> int:
    """A typo'd key would silently drop a client's real positioning."""
    try:
        brand.from_dict(
            {
                "slug": "typo",
                "name": "Typo Co",
                "site_url": "https://typo.example",
                "author_name": "A Person",
                "postioning": "misspelled on purpose",
                "proof_points": [
                    {"label": "a", "pattern": "a", "source": "s"},
                    {"label": "b", "pattern": "b", "source": "s"},
                ],
                "competitors": ["One", "Two"],
            }
        )
    except ProfileError as exc:
        if "postioning" not in str(exc):
            _fail(f"error should name the offending key, got: {exc}")
            return 1
        return 0
    _fail("an unknown key was silently ignored")
    return 1


def test_a_bad_regex_is_refused() -> int:
    try:
        brand.from_dict(
            {
                "slug": "badre",
                "name": "Bad Regex Co",
                "site_url": "https://badre.example",
                "author_name": "A Person",
                "proof_points": [
                    {"label": "broken", "pattern": "(unclosed", "source": "s"},
                    {"label": "fine", "pattern": r"\b7\b", "source": "s"},
                ],
                "competitors": ["One", "Two"],
            }
        )
    except ProfileError:
        return 0
    _fail("an invalid regex was accepted and would crash the gate at publish time")
    return 1


# ── The gate, running for someone else ────────────────────────────────────────────────────
def test_the_gate_passes_a_compliant_post_for_another_brand() -> int:
    report = geo.audit(_acme_post(), profile=ACME)
    if not report.ok:
        _fail(f"a compliant Chairside post was rejected: {report.failures}")
        return 1
    return 0


def test_a_post_written_for_us_fails_another_brands_gate() -> int:
    """The load-bearing test. Evidence is per-tenant or it is decoration.

    A Buteforce post carries 99.2%, 120 items/min and names Cognex and Keyence. Under
    Chairside's profile none of those are proof points and none of those are competitors, so
    the post must fail on BOTH counts — not squeak through on structure alone.
    """
    buteforce_post = (
        '---\ntitle: "QC"\ndescription: "Meta."\ndate: "2026-08-04"\n'
        'author: "Dhyaneshwaran"\ndateModified: "2026-08-04"\n---\n\n'
        "## How accurate is automated visual inspection?\n\n"
        "Automated visual inspection on a production line reaches 99.2% classification "
        "accuracy at 120 items/min on the ortho-classifier deployment, measured over a full "
        "acceptance run rather than a demo reel. That figure holds because the model is "
        "trained on the line's own defect population instead of a generic dataset, which is "
        "the difference between a benchmark number and one that survives contact with a "
        "real shift.\n\n"
        "## What does a vision system cost to run?\n\n"
        "A production vision system costs far less to run than to build, because inference "
        "sits on a single edge box per line and the recurring spend is maintenance rather "
        "than licence fees. The build is where the engineering goes: fixturing, lighting, "
        "and the defect taxonomy that decides what the model is even looking for on that "
        "particular line.\n\n"
        "| Option | Best for | Where it wins |\n"
        "|---|---|---|\n"
        "| Cognex | Standard inspections | Off-the-shelf sensor reliability |\n"
        "| Keyence | Fast deployment | Vendor support and tuning |\n"
        "| Custom build | Unusual defects | Fits a defect set no sensor ships with |\n\n"
        "## Not a fit if\n\n" + _words(50) + "\n"
    )

    failures = 0
    if geo.audit(buteforce_post, profile=brand.load("buteforce")).ok is False:
        _fail("fixture problem: this post should pass the Buteforce gate")
        failures += 1

    report = geo.audit(buteforce_post, profile=ACME)
    if report.ok:
        _fail("a Buteforce post passed Chairside's gate — evidence is not tenant-bound")
        return failures + 1

    joined = " ".join(report.failures).lower()
    if "proof number" not in joined:
        _fail(f"expected a proof-number failure under the other profile, got: {report.failures}")
        failures += 1
    if "competitor" not in joined:
        _fail(f"expected a competitor failure under the other profile, got: {report.failures}")
        failures += 1
    return failures


def test_the_repair_brief_names_the_right_brand() -> int:
    """The brief goes back to an LLM. If it says 'Buteforce' to a client's writer, we ship
    another brand's identity into their draft."""
    naked = '---\ntitle: "X"\ndateModified: "2026-08-04"\nauthor: "Priya Raghunathan"\n---\n\nJust prose.\n'
    brief = geo.audit(naked, profile=ACME).as_brief()
    failures = 0
    if "Buteforce" in brief:
        _fail("the repair brief for Chairside mentions Buteforce")
        failures += 1
    if "Chairside" not in brief:
        _fail("the repair brief never names the brand it is written for")
        failures += 1
    if "Dentrix" not in brief and "Curve Dental" not in brief:
        _fail("the repair brief suggests no competitor from this brand's own list")
        failures += 1
    return failures


def test_template_rules_are_brand_specific() -> int:
    """The prompt half and the gate half must come from the same profile, or they drift."""
    rules = geo.template_rules(ACME)
    failures = 0
    for ours in ("Buteforce", "99.2", "Cognex"):
        if ours in rules:
            _fail(f"Chairside's writer prompt leaks {ours!r} from our profile")
            failures += 1
    for theirs in ("Chairside", "31% fewer no-shows", "Dentrix"):
        if theirs not in rules:
            _fail(f"Chairside's writer prompt is missing {theirs!r}")
            failures += 1
    return failures


def test_legacy_module_constants_still_resolve() -> int:
    """Existing callers read `geo.AUTHOR_NAME` etc. They must keep working, via the profile."""
    failures = 0
    if geo.AUTHOR_NAME != brand.load("buteforce").author_name:
        _fail("geo.AUTHOR_NAME no longer matches the active profile")
        failures += 1
    if "99.2% vision accuracy" not in geo.PROOF_NUMBERS:
        _fail("geo.PROOF_NUMBERS lost its legacy {label: pattern} shape")
        failures += 1
    if geo.MIN_TABLE_BODY_ROWS != 3:
        _fail(f"geo.MIN_TABLE_BODY_ROWS is {geo.MIN_TABLE_BODY_ROWS}, expected 3")
        failures += 1
    try:
        geo.NOT_A_REAL_CONSTANT  # noqa: B018
    except AttributeError:
        pass
    else:
        _fail("an unknown module attribute resolved instead of raising AttributeError")
        failures += 1
    return failures


def main() -> int:
    tests = [
        ("shipped Buteforce profile validates", test_the_real_profile_loads_and_validates),
        ("profile that cannot pass its own gate refused", test_a_profile_that_cannot_pass_its_own_gate_is_refused),
        ("proof point without provenance refused", test_a_proof_point_without_provenance_is_refused),
        ("unknown key refused, not ignored", test_an_unknown_key_is_refused_not_ignored),
        ("invalid regex refused", test_a_bad_regex_is_refused),
        ("gate passes another brand's compliant post", test_the_gate_passes_a_compliant_post_for_another_brand),
        ("our post fails another brand's gate", test_a_post_written_for_us_fails_another_brands_gate),
        ("repair brief names the right brand", test_the_repair_brief_names_the_right_brand),
        ("template rules are brand-specific", test_template_rules_are_brand_specific),
        ("legacy module constants still resolve", test_legacy_module_constants_still_resolve),
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
