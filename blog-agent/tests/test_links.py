"""Link normalisation tests.

Published posts were polluted with three defects the linker prompt alone could
not prevent: absolute `www.buteforce.com` internal links (each one a 308 hop),
invented `/blog/<slug>` URLs for posts that do not exist, and "citations" that
pointed at a company homepage instead of the page carrying the claim.

`swarm.links.normalise_links` fixes all three deterministically, after the LLM
has run, so a prompt regression cannot reintroduce them.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm.links import normalise_links  # noqa: E402

KNOWN_SLUGS = {"yolov8-manufacturing", "death-of-pilot-projects"}
CITED_URLS = {"https://sparktoro.com/blog/2024-zero-click-search-study/"}


def _norm(mdx: str):
    return normalise_links(mdx, known_slugs=KNOWN_SLUGS, cited_urls=CITED_URLS)


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


def test_www_internal_becomes_relative() -> int:
    failures = 0
    cases = {
        "See [our services](https://www.buteforce.com/services/automation) today.":
            "See [our services](/services/automation) today.",
        "Read [the guide](https://buteforce.com/blog/yolov8-manufacturing) now.":
            "Read [the guide](/blog/yolov8-manufacturing) now.",
        "Visit [contact](https://www.buteforce.com/contact).":
            "Visit [contact](/contact).",
    }
    for src, expected in cases.items():
        got, _ = _norm(src)
        if got != expected:
            _fail(f"expected {expected!r}, got {got!r}")
            failures += 1
    return failures


def test_phantom_blog_link_is_unwrapped() -> int:
    """A link to a slug that was never published loses the link, keeps the text."""
    failures = 0
    src = "As covered in [our earlier piece](/blog/this-post-never-existed), the data is clear."
    got, report = _norm(src)
    if "](" in got:
        _fail(f"phantom link survived: {got!r}")
        failures += 1
    if "our earlier piece" not in got:
        _fail(f"anchor text was destroyed: {got!r}")
        failures += 1
    if not report["phantom_internal"]:
        _fail("phantom link was not reported")
        failures += 1
    return failures


def test_real_blog_link_survives() -> int:
    failures = 0
    src = "See [the YOLOv8 post](/blog/yolov8-manufacturing) for detail."
    got, _ = _norm(src)
    if got != src:
        _fail(f"valid link was altered: {got!r}")
        failures += 1
    return failures


def test_homepage_citation_is_unwrapped() -> int:
    """A bare homepage is not evidence for a claim — strip the link, keep the words."""
    failures = 0
    src = "Adoption hit 60% [according to McKinsey](https://www.mckinsey.com)."
    got, report = _norm(src)
    if "](" in got:
        _fail(f"homepage citation survived: {got!r}")
        failures += 1
    if "according to McKinsey" not in got:
        _fail(f"anchor text was destroyed: {got!r}")
        failures += 1
    if not report["homepage_citations"]:
        _fail("homepage citation was not reported")
        failures += 1
    return failures


def test_uncited_external_is_unwrapped() -> int:
    """External URLs the research never surfaced are hallucination risk."""
    failures = 0
    src = "Per [this study](https://example.com/some/invented/report), output doubled."
    got, report = _norm(src)
    if "](" in got:
        _fail(f"uncited external link survived: {got!r}")
        failures += 1
    if not report["uncited_external"]:
        _fail("uncited external link was not reported")
        failures += 1
    return failures


def test_cited_external_survives() -> int:
    failures = 0
    src = "Per [SparkToro](https://sparktoro.com/blog/2024-zero-click-search-study/), 68% end without a click."
    got, _ = _norm(src)
    if got != src:
        _fail(f"legitimate citation was altered: {got!r}")
        failures += 1
    return failures


def test_frontmatter_and_images_untouched() -> int:
    failures = 0
    src = (
        '---\ntitle: "Test"\nimage: "https://www.buteforce.com/img/hero.png"\n---\n\n'
        "Body with ![hero](https://cdn.example.com/hero.png) image.\n"
    )
    got, _ = _norm(src)
    if 'image: "https://www.buteforce.com/img/hero.png"' not in got:
        _fail("frontmatter was rewritten")
        failures += 1
    if "![hero](https://cdn.example.com/hero.png)" not in got:
        _fail("image embed was rewritten")
        failures += 1
    return failures


def test_query_tagged_internal_link_survives() -> int:
    """A UTM-tagged internal link is still an internal link.

    `_internal_path_ok` stripped only the fragment, never the query, so any internal link
    carrying a query param missed the KNOWN_PATHS lookup and was unwrapped — silently, since
    unwrapping keeps the anchor text and drops only the href. That made blog-to-landing-page
    attribution impossible to add: the untagged link survived and the tagged one vanished.
    """
    failures = 0
    for url in ("/lp/ai-audit?utm_source=blog&utm_medium=cta",
                "/services?ref=post",
                "/lp/ai-audit?utm_source=blog#book"):
        out, report = normalise_links(f"Text [Book an audit]({url}) here.")
        if url not in out:
            _fail(f"a tagged internal link was stripped: {url} ({report['phantom_internal']})")
            failures += 1
    # And the rule still bites: a query string must not smuggle an unknown path through.
    out, _ = normalise_links("Go [here](/not-a-real-page?utm_source=blog).")
    if "/not-a-real-page" in out:
        _fail("a query string let an unknown internal path past the validator")
        failures += 1
    return failures


def main() -> int:
    tests = [
        ("www internal links become relative", test_www_internal_becomes_relative),
        ("phantom /blog/ link unwrapped", test_phantom_blog_link_is_unwrapped),
        ("real /blog/ link survives", test_real_blog_link_survives),
        ("homepage citation unwrapped", test_homepage_citation_is_unwrapped),
        ("query-tagged internal link survives", test_query_tagged_internal_link_survives),
        ("uncited external unwrapped", test_uncited_external_is_unwrapped),
        ("cited external survives", test_cited_external_survives),
        ("frontmatter and images untouched", test_frontmatter_and_images_untouched),
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
