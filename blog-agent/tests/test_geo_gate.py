"""GEO template gate tests.

The gate exists because AI Visibility SCAN 001 measured 0/18 citations while the writer prompt
already banned puffery and asked for structure. So the tests that matter are the adversarial
ones: a draft that *looks* compliant must still fail when the structure is decorative.

`swarm/geo.py` is import-clean (no supabase, no ADK, no dotenv), so these import it directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm import brand, geo, links  # noqa: E402


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


def _words(n: int) -> str:
    return " ".join(["inspection"] * n)


FRONTMATTER = (
    '---\ntitle: "A Post"\ndescription: "Meta."\ndate: "2026-07-26"\ntags: ["cv"]\n---\n\n'
)

TABLE = """
| Option | Accuracy | Where it wins |
|---|---|---|
| Cognex In-Sight | High | Off-the-shelf reliability, global support |
| Keyence | High | Fastest sensor-level setup |
| Buteforce custom YOLOv8 | 99.2% | Defects no catalogue model was trained on |
"""

NOT_A_FIT = f"## Not a fit if you run one line under 20 packs a minute\n\n{_words(60)}\n"


def _compliant_body() -> str:
    return (
        f"# A Post\n\n{_words(80)}\n\n"
        f"## What does computer vision inspection actually cost on an Indian FMCG line?\n\n"
        f"{_words(70)}\n\nElaboration paragraph. {_words(120)}\n\n"
        f"## How fast can a vision system run before accuracy drops?\n\n"
        f"{_words(90)}\n\nMore detail here. {_words(150)}\n\n"
        f"## The throughput reality\n\nWe hold 99.2% at 120 items/min. {_words(200)}\n\n"
        f"{TABLE}\n\n{NOT_A_FIT}\n"
    )


def _compliant() -> str:
    """A post shaped exactly as the pipeline emits one: authored body, then every
    deterministic requirement injected (5, 6 and 7)."""
    return geo.inject_deterministic(FRONTMATTER + _compliant_body())


# ── Baseline ──────────────────────────────────────────────────────────────────────────────
def test_compliant_post_passes() -> int:
    report = geo.audit(_compliant())
    if not report.ok:
        _fail(f"a compliant post was rejected: {report.failures}")
        return 1
    if report.question_answers < geo.MIN_QUESTION_H2:
        _fail(f"counted only {report.question_answers} compliant Q&A blocks")
        return 1
    return 0


# ── Requirement 1: question H2 + self-contained answer ────────────────────────────────────
def test_statement_headings_fail() -> int:
    mdx = _compliant().replace(
        "## What does computer vision inspection actually cost on an Indian FMCG line?",
        "## The cost of computer vision inspection",
    ).replace(
        "## How fast can a vision system run before accuracy drops?",
        "## Throughput and accuracy",
    )
    if geo.audit(mdx).ok:
        _fail("a post with no question-form H2 passed")
        return 1
    return 0


def test_decorative_question_heading_fails() -> int:
    """A question H2 with a one-line stub under it is the obvious way to game this."""
    stub = (
        f"# A Post\n\n{_words(80)}\n\n"
        f"## What does it cost?\n\nIt depends on the line.\n\n"
        f"## How fast is it?\n\nVery fast.\n\n"
        f"## Detail\n\n99.2% at 120 items/min. {_words(400)}\n\n{TABLE}\n\n{NOT_A_FIT}\n"
    )
    report = geo.audit(geo.inject_metadata(FRONTMATTER + stub))
    if report.ok:
        _fail("question headings with stub answers passed the gate")
        return 1
    if report.question_answers != 0:
        _fail(f"stub answers were counted as compliant ({report.question_answers})")
        return 1
    return 0


def test_answer_must_be_prose_not_a_list() -> int:
    """Answer engines quote sentences; a bullet list directly under the heading is not an answer."""
    listy = _compliant().replace(
        f"## How fast can a vision system run before accuracy drops?\n\n{_words(90)}",
        "## How fast can a vision system run before accuracy drops?\n\n"
        + "\n".join(f"- point {i} {_words(12)}" for i in range(6)),
    )
    if geo.audit(listy).ok:
        _fail("a bullet list directly under a question H2 was accepted as the answer")
        return 1
    return 0


def test_overlong_answer_fails() -> int:
    """Past ~160 words it stops being a quotable snippet."""
    bloated = _compliant().replace(
        f"## How fast can a vision system run before accuracy drops?\n\n{_words(90)}",
        f"## How fast can a vision system run before accuracy drops?\n\n{_words(400)}",
    )
    if geo.audit(bloated).ok:
        _fail("a 400-word answer block passed the 40-160 word window")
        return 1
    return 0


def test_h3_question_does_not_count() -> int:
    """The requirement is H2 — that is the level answer engines lift as a heading."""
    demoted = _compliant().replace("## What does computer vision", "### What does computer vision")
    if geo.audit(demoted).ok:
        _fail("an H3 question was counted toward the H2 requirement")
        return 1
    return 0


# ── Requirement 2: hard numbers, never adjectives ─────────────────────────────────────────
def test_missing_proof_numbers_fails() -> int:
    numberless = _compliant().replace("99.2% at 120 items/min", "extremely accurate at high speed")
    report = geo.audit(numberless)
    if report.ok:
        _fail("a post with no hard proof numbers passed")
        return 1
    return 0


def test_throughput_number_variants_are_recognised() -> int:
    failures = 0
    pattern = geo.PROOF_NUMBERS["120 items/min throughput"]
    for variant in ["120 items/min", "120 items per minute", "120 packs/min",
                    "120 CPM", "120/min", "120 units a minute"]:
        if not pattern.search(variant):
            _fail(f"throughput variant not recognised: {variant!r}")
            failures += 1
    if pattern.search("120 defects found"):
        _fail("throughput pattern matched an unrelated '120'")
        failures += 1
    return failures


def test_rounded_number_does_not_satisfy_the_gate() -> int:
    """'over 99%' is the tell that the writer paraphrased instead of quoting the real figure."""
    rounded = _compliant().replace(
        "We hold 99.2% at 120 items/min.", "We hold over 99% accuracy at high line speed.",
    )
    if geo.audit(rounded).ok:
        _fail("'over 99%' was accepted in place of 99.2% / 120 items/min")
        return 1
    return 0


def test_banned_adjectives_fail() -> int:
    failures = 0
    for adjective in ["world-class", "cutting-edge", "revolutionary", "game-changing",
                      "state-of-the-art", "transformative"]:
        mdx = _compliant().replace("## The throughput reality",
                                   f"## The {adjective} throughput reality")
        report = geo.audit(mdx)
        if report.ok:
            _fail(f"banned adjective passed the gate: {adjective}")
            failures += 1
    return failures


def test_live_fmcg_post_fails_the_gate() -> int:
    """Regression anchor: the real page that earns ~60% of visibility must not pass as-is.

    Its actual copy — 'Revolutionizing', 'game-changer', 'seismic shift', no comparison table,
    no disqualifier, no question headings — is what the gate was built to stop.
    """
    live = (
        '---\ntitle: "AI-Driven Quality Control: Revolutionizing FMCG Manufacturing in India"\n'
        'description: "Explore how computer vision is transforming quality control."\n'
        'date: "2026-07-04"\ntags: ["Computer Vision"]\n---\n\n'
        "# AI-Driven Quality Control: Revolutionizing FMCG Manufacturing in India\n\n"
        f"{_words(200)}\n\n## The Current Landscape of FMCG in India\n\n{_words(200)}\n\n"
        f"## Conclusion: Embracing a Smart Future\n\nThis is a game-changer and a seismic "
        f"shift. {_words(200)}\n"
    )
    if geo.audit(live).ok:
        _fail("the live FMCG post passed the gate — the gate is not enforcing anything")
        return 1
    return 0


# ── Requirement 3: competitor-inclusive comparison table ──────────────────────────────────
def test_missing_table_fails() -> int:
    if geo.audit(_compliant().replace(TABLE, "")).ok:
        _fail("a post with no comparison table passed")
        return 1
    return 0


def test_table_without_named_competitors_fails() -> int:
    """'Us vs. a generic alternative' is a brochure, not a comparison."""
    vague = _compliant().replace(TABLE, """
| Option | Accuracy | Where it wins |
|---|---|---|
| Off-the-shelf tools | Medium | Cheap to start |
| In-house build | Varies | Full control |
| Buteforce | 99.2% | Custom defects |
""")
    if geo.audit(vague).ok:
        _fail("a table naming zero real competitors passed")
        return 1
    return 0


def test_one_vendor_under_two_spellings_fails() -> int:
    """Two spellings of one vendor is one competitor, not two.

    The registry used to carry both "Omron" and "OMRON". A table naming Omron once matched
    both entries and scored two competitors, so it passed the very check that had just
    rejected an honest draft for naming only one.
    """
    one_vendor = _compliant().replace(TABLE, """
| Option | Accuracy | Where it wins |
|---|---|---|
| Omron | High | Off-the-shelf reliability |
| OMRON sensors | High | Sensor-level setup |
| Buteforce custom YOLOv8 | 99.2% | Defects no catalogue model was trained on |
""")
    if geo.audit(one_vendor).ok:
        _fail("a table naming one vendor under two spellings passed the 2-competitor minimum")
        return 1
    return 0


def test_vendor_alias_is_recognised() -> int:
    """A draft that wrote "AWS Textract" names Amazon Textract, and the gate must know it."""
    named = brand.active().named_competitors("we benchmarked AWS Textract against Nanonets")
    failures = 0
    if "Amazon Textract" not in named:
        _fail(f"alias 'AWS Textract' was not recognised — got {named}")
        failures += 1
    if "Nanonets" not in named:
        _fail(f"'Nanonets' was not recognised — got {named}")
        failures += 1
    return failures


def test_failure_message_names_candidates() -> int:
    """A repair brief that does not say WHICH vendors to add cannot be acted on.

    The pipeline allows exactly one repair attempt, so an unactionable brief burns it.
    """
    vague = _compliant().replace(TABLE, """
| Option | Accuracy | Where it wins |
|---|---|---|
| Off-the-shelf tools | Medium | Cheap to start |
| In-house build | Varies | Full control |
| Buteforce | 99.2% | Custom defects |
""")
    report = geo.audit(vague, cluster="document-ai")
    brief = " ".join(report.failures)
    if "Nanonets" not in brief and "Rossum" not in brief:
        _fail("the table failure suggests no vendor from the post's own cluster")
        return 1
    return 0


def test_writer_is_shown_the_cluster_shortlist() -> int:
    """The writer must SEE the closed vocabulary it is being graded against."""
    failures = 0
    rules = geo.template_rules(cluster="document-ai")
    if "Nanonets" not in rules:
        _fail("the document-AI writer prompt never names a document-AI vendor")
        failures += 1
    if "Cognex" in rules:
        _fail("the document-AI writer prompt leaks machine-vision vendors")
        failures += 1
    return failures


def test_two_row_table_fails() -> int:
    thin = _compliant().replace(TABLE, """
| Option | Where it wins |
|---|---|
| Cognex | Off-the-shelf reliability |
| Keyence | Sensor-level setup |
""")
    if geo.audit(thin).ok:
        _fail(f"a {geo.MIN_TABLE_BODY_ROWS - 1}-row table passed the row minimum")
        return 1
    return 0


def test_competitor_named_outside_a_table_does_not_count() -> int:
    """Prose name-drops are not a comparison; the table is the citable artefact."""
    prose_only = _compliant().replace(TABLE, "").replace(
        "## The throughput reality",
        "## Cognex and Keyence both sell this, but\n\nWe hold 99.2% at 120 items/min. "
        f"{_words(100)}\n\n## The throughput reality",
    )
    if geo.audit(prose_only).ok:
        _fail("competitors named only in prose satisfied the table requirement")
        return 1
    return 0


def test_ai_coding_tool_competitors_are_recognized() -> int:
    """Regression, 2026-08-02: the ideator news-jacked the AI-coding-tools vertical
    (Sarvam Code vs. Claude Code vs. Codex) and COMPETITORS had zero vocabulary for
    it — every post in that category failed the gate on the first attempt because
    none of the three names a reader would expect were on the recognized list.
    """
    coding_table = """
| Tool | Hosting | Where it wins |
|---|---|---|
| Sarvam Code | India-hosted | Cost per task |
| Claude Code | Terminal-native | Local, real-time integration |
| Codex | Cloud | Broader delegation, workflow automation |
"""
    report = geo.audit(_compliant().replace(TABLE, coding_table))
    if not report.ok:
        _fail(f"a table naming Sarvam Code / Claude Code / Codex was rejected: {report.failures}")
        return 1
    return 0


def test_multiple_tables_one_compliant_passes() -> int:
    """A spec table plus a real comparison table must not be penalised."""
    extra = "\n| Camera | Lens |\n|---|---|\n| Basler | 16mm |\n\n"
    if not geo.audit(_compliant().replace(TABLE, extra + TABLE)).ok:
        _fail("a post with an extra non-comparison table was rejected")
        return 1
    return 0


# ── Requirement 4: explicit disqualification ──────────────────────────────────────────────
def test_missing_not_a_fit_fails() -> int:
    if geo.audit(_compliant().replace(NOT_A_FIT, "")).ok:
        _fail("a post with no 'not a fit if' section passed")
        return 1
    return 0


def test_token_not_a_fit_section_fails() -> int:
    token = _compliant().replace(NOT_A_FIT, "## Not a fit if you are small\n\nCall us anyway.\n")
    if geo.audit(token).ok:
        _fail("a one-line disqualifier passed")
        return 1
    return 0


def test_not_a_fit_phrasings_are_recognised() -> int:
    failures = 0
    for heading in ["Not a fit if you run a single line",
                    "When not to buy a vision system",
                    "Who shouldn't call us",
                    "When this doesn't work",
                    "Where this breaks down"]:
        mdx = _compliant().replace(
            "## Not a fit if you run one line under 20 packs a minute", f"## {heading}",
        )
        if not geo.audit(mdx).ok:
            _fail(f"valid disqualifier phrasing rejected: {heading!r}")
            failures += 1
    return failures


# ── Requirements 5 + 6: injected metadata ─────────────────────────────────────────────────
def test_metadata_injection() -> int:
    failures = 0
    out = geo.inject_metadata(FRONTMATTER + "# X\n\nbody", date_modified="2026-07-26")
    if 'dateModified: "2026-07-26"' not in out:
        _fail("dateModified was not injected")
        failures += 1
    if f'author: "{geo.AUTHOR_NAME}"' not in out:
        _fail("author was not injected")
        failures += 1
    if "# X\n\nbody" not in out:
        _fail("injection corrupted the body")
        failures += 1
    return failures


def test_injection_is_idempotent_and_refreshes_the_date() -> int:
    failures = 0
    once = geo.inject_metadata(FRONTMATTER + "# X\n\nbody", date_modified="2026-07-01")
    twice = geo.inject_metadata(once, date_modified="2026-07-26")
    if twice.count("dateModified:") != 1 or twice.count("author:") != 1:
        _fail("re-injection duplicated frontmatter keys")
        failures += 1
    if 'dateModified: "2026-07-26"' not in twice:
        _fail("dateModified was not refreshed on re-injection")
        failures += 1
    if '2026-07-01' in twice:
        _fail("stale dateModified survived")
        failures += 1
    return failures


def test_injection_preserves_an_existing_author() -> int:
    guest = '---\ntitle: "X"\nauthor: "Guest Writer"\n---\n\nbody'
    if 'author: "Guest Writer"' not in geo.inject_metadata(guest):
        _fail("an upstream author byline was overwritten")
        return 1
    return 0


def test_missing_metadata_is_reported() -> int:
    """Audit catches a skipped injection rather than trusting the caller."""
    report = geo.audit(FRONTMATTER + _compliant_body())
    if not any("author" in f for f in report.failures):
        _fail("missing author was not reported")
        return 1
    if not any("dateModified" in f for f in report.failures):
        _fail("missing dateModified was not reported")
        return 1
    return 0


# ── Parser robustness ─────────────────────────────────────────────────────────────────────
def test_headings_inside_code_fences_are_ignored() -> int:
    fenced = _compliant().replace(
        "## The throughput reality",
        "```python\n# not a heading\n## also not a heading?\n```\n\n## The throughput reality",
    )
    if not geo.audit(fenced).ok:
        _fail("a fenced code block was parsed as headings")
        return 1
    return 0


def test_repair_brief_names_every_failure() -> int:
    bare = FRONTMATTER + f"# X\n\n## Overview\n\n{_words(1200)}\n"
    report = geo.audit(bare)
    brief = report.as_brief()
    failures = 0
    if len(report.failures) < 4:
        _fail(f"expected 4+ failures on an empty-template post, got {len(report.failures)}")
        failures += 1
    for expected in ["question-form", "proof number", "comparison table", "not a fit"]:
        if expected not in brief.lower():
            _fail(f"repair brief never mentions {expected!r}")
            failures += 1
    return failures


# ── Requirement 7: a working conversion link ──────────────────────────────────────────────
def test_cta_is_injected_with_a_real_link() -> int:
    """The measured failure: 38 posts, two links to the page that converts, zero key events."""
    f = 0
    p = brand.active()
    out = _compliant()
    if f"]({p.cta_path})" not in out:
        _fail("the CTA link was not injected into the body")
        f += 1
    if p.cta_label not in out:
        _fail("the CTA label is missing")
        f += 1
    if not geo.audit(out).ok:
        _fail(f"an injected CTA did not satisfy the gate: {geo.audit(out).failures}")
        f += 1
    return f


def test_a_post_with_no_cta_link_fails() -> int:
    f = 0
    without = geo.inject_metadata(FRONTMATTER + _compliant_body())
    report = geo.audit(without)
    if report.ok:
        _fail("a post with no link to the conversion path passed the gate")
        f += 1
    if not any("no link to" in x for x in report.failures):
        _fail(f"the failure does not name the missing CTA: {report.failures}")
        f += 1
    return f


def test_prose_describing_a_cta_is_not_a_cta() -> int:
    """The exact shape all 38 published posts ended in: a sentence, not a destination."""
    f = 0
    body = _compliant_body() + (
        "\n\nIf this is your bottleneck, Buteforce can help you scope it. "
        "Bring the workflow and we will tell you plainly whether it should be built.\n"
    )
    mdx = geo.inject_metadata(FRONTMATTER + body)
    if geo.audit(mdx).ok:
        _fail("a prose sign-off with no link passed as a conversion path")
        f += 1
    return f


def test_cta_injection_is_idempotent() -> int:
    """Four points in the pipeline re-finalise a draft; none may stack a second CTA."""
    f = 0
    once = _compliant()
    twice = geo.inject_deterministic(geo.inject_deterministic(once))
    if twice.count(geo._CTA_MARKER) != 2:
        _fail(f"expected one marked block, found {twice.count(geo._CTA_MARKER) // 2}")
        f += 1
    if twice.count(brand.active().cta_label) != 1:
        _fail("the CTA was duplicated across repeated injection")
        f += 1
    if not geo.audit(twice).ok:
        _fail(f"a twice-injected post failed the gate: {geo.audit(twice).failures}")
        f += 1
    return f


def test_cta_injection_preserves_frontmatter_and_body() -> int:
    f = 0
    out = _compliant()
    if not out.lstrip().startswith("---"):
        _fail("frontmatter delimiters were lost during CTA injection")
        f += 1
    if "## Not a fit if" not in out:
        _fail("the authored body did not survive CTA injection")
        f += 1
    fm, _ = geo.split_frontmatter(out)
    if "dateModified" not in fm or "author" not in fm:
        _fail("metadata injection did not survive alongside the CTA")
        f += 1
    return f


def test_injected_cta_cannot_satisfy_an_authored_requirement() -> int:
    """The gate must not grade its own injection.

    The CTA block is appended after the last authored section — normally "not a fit if…" —
    so before `_strip_cta` its ~30 words counted toward that section's 40-word minimum, and a
    one-line disqualifier passed requirement 4 on text the writer never produced. Caught by
    the existing token-disqualifier test the first time the CTA shipped.
    """
    f = 0
    thin = _compliant().replace(NOT_A_FIT, "## Not a fit if you are tiny\n\nToo small.\n")
    report = geo.audit(thin)
    if report.ok:
        _fail("a one-line disqualifier passed because the injected CTA padded the section")
        f += 1
    if not any("only" in x and "words" in x for x in report.failures):
        _fail(f"the word-count failure was not reported: {report.failures}")
        f += 1
    return f


def test_cta_survives_the_link_validator() -> int:
    """A UTM-tagged internal link is still an internal link.

    `_internal_path_ok` used to strip only the fragment, so a tagged CTA failed the
    KNOWN_PATHS lookup and was unwrapped — silently, since unwrapping keeps the anchor
    text. Attribution was impossible to add for exactly that reason.
    """
    f = 0
    cleaned, report = links.normalise_links(_compliant(), known_slugs=set(), cited_urls=set())
    if brand.active().cta_path not in cleaned:
        _fail(f"the link validator stripped the CTA: {report['phantom_internal']}")
        f += 1
    if not geo.audit(cleaned).ok:
        _fail(f"the post failed the gate after link validation: {geo.audit(cleaned).failures}")
        f += 1
    return f



def main() -> int:
    tests = [
        ("compliant post passes", test_compliant_post_passes),
        ("statement headings fail", test_statement_headings_fail),
        ("decorative question heading fails", test_decorative_question_heading_fails),
        ("answer must be prose, not a list", test_answer_must_be_prose_not_a_list),
        ("overlong answer fails", test_overlong_answer_fails),
        ("H3 question does not count", test_h3_question_does_not_count),
        ("missing proof numbers fail", test_missing_proof_numbers_fails),
        ("throughput variants recognised", test_throughput_number_variants_are_recognised),
        ("rounded number does not satisfy gate", test_rounded_number_does_not_satisfy_the_gate),
        ("banned adjectives fail", test_banned_adjectives_fail),
        ("live FMCG post fails the gate", test_live_fmcg_post_fails_the_gate),
        ("missing table fails", test_missing_table_fails),
        ("table without named competitors fails", test_table_without_named_competitors_fails),
        ("one vendor under two spellings fails", test_one_vendor_under_two_spellings_fails),
        ("vendor alias recognised", test_vendor_alias_is_recognised),
        ("failure message names candidates", test_failure_message_names_candidates),
        ("writer shown the cluster shortlist", test_writer_is_shown_the_cluster_shortlist),
        ("two-row table fails", test_two_row_table_fails),
        ("competitor in prose does not count", test_competitor_named_outside_a_table_does_not_count),
        ("AI coding-tool competitors recognised", test_ai_coding_tool_competitors_are_recognized),
        ("extra non-comparison table tolerated", test_multiple_tables_one_compliant_passes),
        ("missing 'not a fit' fails", test_missing_not_a_fit_fails),
        ("token 'not a fit' fails", test_token_not_a_fit_section_fails),
        ("'not a fit' phrasings recognised", test_not_a_fit_phrasings_are_recognised),
        ("metadata injected", test_metadata_injection),
        ("injection idempotent, date refreshed", test_injection_is_idempotent_and_refreshes_the_date),
        ("existing author preserved", test_injection_preserves_an_existing_author),
        ("missing metadata reported", test_missing_metadata_is_reported),
        ("code fences ignored", test_headings_inside_code_fences_are_ignored),
        ("repair brief names every failure", test_repair_brief_names_every_failure),
        ("CTA injected with a real link", test_cta_is_injected_with_a_real_link),
        ("no CTA link fails", test_a_post_with_no_cta_link_fails),
        ("prose describing a CTA is not a CTA", test_prose_describing_a_cta_is_not_a_cta),
        ("CTA injection idempotent", test_cta_injection_is_idempotent),
        ("CTA injection preserves the post", test_cta_injection_preserves_frontmatter_and_body),
        ("injected CTA cannot satisfy an authored rule", test_injected_cta_cannot_satisfy_an_authored_requirement),
        ("CTA survives the link validator", test_cta_survives_the_link_validator),
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
