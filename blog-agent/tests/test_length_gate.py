"""Draft length gate tests.

`_body_word_count` must ignore frontmatter — counting it inflated short drafts
past the floor and was part of why five ~550-word posts shipped unnoticed after
the 2026-06-29 gpt-4o switch.

The expansion pass is the second lesson. Re-asking the writer for the whole post
"but longer" does not work (2026-08-02: 634 → 764 words against an 1,100 floor,
run failed), so the gate now grows the draft one `##` section at a time. These
tests lift the real functions out of orchestrator.py with `ast` — no supabase,
ADK or network — and drive them with a scripted writer.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_gate():
    """Import the gate helpers without pulling in supabase/ADK/dotenv."""
    import ast
    import re
    import types

    source = (Path(__file__).resolve().parents[1] / "swarm" / "orchestrator.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    wanted = {
        "_body_word_count", "_split_head_body", "_split_body_sections",
        "_clean_expanded_section",
        "MIN_BODY_WORDS", "_LENGTH_RETRIES", "_LENGTH_TARGET_WORDS",
        "_SECTION_TARGET_WORDS", "_SECTION_MAX_WORDS", "_MAX_EXPANSION_CALLS",
        "_MIN_SECTION_GROWTH", "_FRONTMATTER_BLOCK", "_H2_LINE",
    }
    # Methods lifted to module level so the tests exercise the shipped code
    # rather than a copy of it that can drift.
    wanted_methods = {"_expand_sections"}

    kept: list[ast.stmt] = []
    for node in tree.body:
        if (isinstance(node, ast.FunctionDef) and node.name in wanted) or (
            isinstance(node, ast.Assign)
            and any(getattr(t, "id", None) in wanted for t in node.targets)
        ):
            kept.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "BlogOrchestrator":
            kept.extend(
                child for child in node.body
                if isinstance(child, ast.FunctionDef) and child.name in wanted_methods
            )

    module = types.ModuleType("gate")
    module.__dict__["re"] = re  # the compiled patterns need it; `import re` was filtered out
    exec(compile(ast.Module(body=kept, type_ignores=[]), "<gate>", "exec"), module.__dict__)
    return module


gate = _load_gate()
FRONTMATTER = '---\ntitle: "A Post"\ndescription: "Ten whole words of metadata sit here."\ntags: ["a"]\n---\n\n'


def _mdx(body_words: int) -> str:
    return FRONTMATTER + " ".join(["word"] * body_words)


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


def _section(heading: str, words: int) -> str:
    return f"## {heading}\n\n" + " ".join(["word"] * words) + "\n\n"


def _post(section_words: list[int], intro_words: int = 60) -> str:
    body = "# A Post\n\n" + " ".join(["word"] * intro_words) + "\n\n"
    body += "".join(_section(f"Section {i}", w) for i, w in enumerate(section_words))
    return FRONTMATTER + body


# ── word counting ────────────────────────────────────────────────────────────
def test_frontmatter_excluded_from_count() -> int:
    failures = 0
    got = gate._body_word_count(_mdx(1200))
    if got != 1200:
        _fail(f"expected 1200 body words, got {got} (frontmatter leaked into the count)")
        failures += 1
    if gate._body_word_count("no frontmatter here") != 3:
        _fail("plain text without frontmatter miscounted")
        failures += 1
    return failures


def test_floor_is_meaningful() -> int:
    """The five posts that shipped thin must fall below the floor."""
    failures = 0
    shipped_thin = [631, 580, 518, 595, 511, 634, 764]  # last two: the 2026-08-02 run
    for words in shipped_thin:
        if gate._body_word_count(_mdx(words)) >= gate.MIN_BODY_WORDS:
            _fail(f"{words}-word post would pass the {gate.MIN_BODY_WORDS} floor")
            failures += 1
    for words in [1301, 1479, 1387, 1204, 1111]:
        if gate._body_word_count(_mdx(words)) < gate.MIN_BODY_WORDS:
            _fail(f"{words}-word post (a good one) would be rejected")
            failures += 1
    return failures


def test_target_clears_floor_with_headroom() -> int:
    """The expansion target must sit above the floor, not on it."""
    failures = 0
    if gate._LENGTH_TARGET_WORDS <= gate.MIN_BODY_WORDS:
        _fail("expansion target is not above the floor — the humaniser will push it back under")
        failures += 1
    if gate._SECTION_MAX_WORDS <= gate._SECTION_TARGET_WORDS:
        _fail("section ceiling is not above the section target")
        failures += 1
    return failures


# ── structural split ─────────────────────────────────────────────────────────
def test_section_split_round_trips() -> int:
    """Reassembly must be byte-exact, or expansion corrupts the post."""
    failures = 0
    _, body = gate._split_head_body(_post([200, 150, 300]))
    preamble, sections = gate._split_body_sections(body)
    if preamble + "".join(sections) != body:
        _fail("preamble + sections did not reproduce the body byte for byte")
        failures += 1
    if len(sections) != 3:
        _fail(f"expected 3 sections, got {len(sections)}")
        failures += 1
    if not preamble.startswith("# A Post"):
        _fail("H1/intro did not stay in the preamble")
        failures += 1
    return failures


def test_head_body_split_keeps_delimiters() -> int:
    failures = 0
    head, body = gate._split_head_body(_post([100]))
    if head + body != _post([100]):
        _fail("head + body did not reproduce the file")
        failures += 1
    if not head.startswith("---") or "title:" not in head:
        _fail("frontmatter block was not captured on the head")
        failures += 1
    if gate._split_head_body("# No frontmatter\n\nbody")[0] != "":
        _fail("invented a frontmatter block where there is none")
        failures += 1
    return failures


def test_h3_stays_with_parent_and_fenced_h2_is_not_a_heading() -> int:
    failures = 0
    body = (
        "# Title\n\nintro\n\n"
        "## Real One\n\ntext\n\n### A Sub\n\nmore text\n\n"
        "```\n## Not A Heading\n```\n\n"
        "## Real Two\n\ntext\n\n"
    )
    preamble, sections = gate._split_body_sections(body)
    if len(sections) != 2:
        _fail(f"expected 2 sections (H3 nested, fenced ## ignored), got {len(sections)}")
        failures += 1
    if "### A Sub" not in sections[0]:
        _fail("H3 was split off from its parent section")
        failures += 1
    if "## Not A Heading" not in sections[0]:
        _fail("a ## inside a code fence was treated as a section break")
        failures += 1
    if preamble + "".join(sections) != body:
        _fail("fence-aware split did not round-trip")
        failures += 1
    return failures


# ── reply cleaning ───────────────────────────────────────────────────────────
def test_clean_expanded_section() -> int:
    failures = 0
    heading = "## Why 40% Of Lines Fail At Night"

    cleaned = gate._clean_expanded_section(
        "Sure! Here is the expanded section:\n\n## A Renamed Heading\n\nthe body text\n", heading
    )
    if not cleaned.startswith(heading):
        _fail("did not restore the original heading (GEO question headings would be renamed)")
        failures += 1
    if "Sure!" in cleaned:
        _fail("leading commentary survived the clean")
        failures += 1
    if "the body text" not in cleaned:
        _fail("dropped the actual body")
        failures += 1

    fenced = gate._clean_expanded_section(
        "```markdown\n## Heading\n\nfenced body\n```", heading
    )
    if "```" in fenced or "fenced body" not in fenced:
        _fail("a fence wrapping the whole reply was not unwrapped")
        failures += 1

    headless = gate._clean_expanded_section("just prose, no heading at all", heading)
    if not headless.startswith(heading) or "just prose" not in headless:
        _fail("a reply without a heading did not get one prepended")
        failures += 1
    return failures


# ── expansion loop ───────────────────────────────────────────────────────────
class _StubWriter:
    """Scripted `_rewrite_section` so the loop runs with no LLM call."""

    def __init__(self, *, grow_to: int | None = 340, refuse: bool = False,
                 runaway: bool = False) -> None:
        self.grow_to = grow_to
        self.refuse = refuse
        self.runaway = runaway
        self.calls = 0
        self.headings: list[str] = []

    def _rewrite_section(self, section: str, target_words: int, writer_prompt: str,
                         topic_id: str, call_no: int) -> str:
        self.calls += 1
        heading = section.splitlines()[0]
        self.headings.append(heading)
        if self.refuse:
            return section
        words = len(section.split()) * 20 if self.runaway else (self.grow_to or target_words)
        return f"{heading}\n\n" + " ".join(["word"] * words) + "\n\n"


def test_expansion_reaches_the_target() -> int:
    failures = 0
    writer = _StubWriter(grow_to=340)
    draft = _post([180, 140, 160, 150, 170])  # ~860 body words — the failing shape
    out = gate._expand_sections(writer, draft, "prompt", "t1")
    words = gate._body_word_count(out)
    if words < gate.MIN_BODY_WORDS:
        _fail(f"expansion stopped at {words} words, still under the {gate.MIN_BODY_WORDS} floor")
        failures += 1
    if writer.calls > gate._MAX_EXPANSION_CALLS:
        _fail(f"made {writer.calls} calls, over the {gate._MAX_EXPANSION_CALLS} cap")
        failures += 1
    if not out.startswith("---") or "title:" not in out:
        _fail("frontmatter was lost during reassembly")
        failures += 1
    return failures


def test_expansion_stops_when_target_met() -> int:
    """A draft already at target must not be touched."""
    failures = 0
    writer = _StubWriter()
    draft = _post([320, 320, 320, 320, 320])
    out = gate._expand_sections(writer, draft, "prompt", "t1")
    if writer.calls != 0:
        _fail(f"expanded a draft that was already long enough ({writer.calls} calls)")
        failures += 1
    if out != draft:
        _fail("rewrote a compliant draft")
        failures += 1
    return failures


def test_expansion_picks_the_thinnest_section_first() -> int:
    failures = 0
    writer = _StubWriter(grow_to=400)
    draft = _post([300, 90, 280])
    gate._expand_sections(writer, draft, "prompt", "t1")
    if not writer.headings or "Section 1" not in writer.headings[0]:
        _fail(f"did not start with the thinnest section (started with {writer.headings[:1]})")
        failures += 1
    return failures


def test_writer_that_will_not_grow_is_bounded() -> int:
    """A refusing writer must stop after one attempt per section, not spin to the cap."""
    failures = 0
    writer = _StubWriter(refuse=True)
    draft = _post([180, 140, 160])
    out = gate._expand_sections(writer, draft, "prompt", "t1")
    if writer.calls != 3:
        _fail(f"expected one attempt per section (3), got {writer.calls}")
        failures += 1
    if gate._body_word_count(out) != gate._body_word_count(draft):
        _fail("a refusing writer still changed the draft")
        failures += 1
    return failures


def test_runaway_reply_is_discarded() -> int:
    """A reply that re-emits the whole post under one heading must not be spliced in."""
    failures = 0
    writer = _StubWriter(runaway=True)
    draft = _post([180, 140, 160])
    out = gate._expand_sections(writer, draft, "prompt", "t1")
    if gate._body_word_count(out) != gate._body_word_count(draft):
        _fail("a runaway expansion reply was accepted and duplicated the article")
        failures += 1
    return failures


def test_no_sections_returns_draft_unchanged() -> int:
    """No `##` headings means nothing to expand — the caller falls back to a rewrite."""
    failures = 0
    writer = _StubWriter()
    draft = FRONTMATTER + "# A Post\n\n" + " ".join(["word"] * 400)
    out = gate._expand_sections(writer, draft, "prompt", "t1")
    if out != draft or writer.calls != 0:
        _fail("tried to expand a draft with no sections")
        failures += 1
    return failures


def main() -> int:
    tests = [
        ("frontmatter excluded from word count", test_frontmatter_excluded_from_count),
        ("floor rejects thin, accepts good posts", test_floor_is_meaningful),
        ("expansion target clears the floor with headroom", test_target_clears_floor_with_headroom),
        ("section split round-trips byte for byte", test_section_split_round_trips),
        ("head/body split keeps delimiters", test_head_body_split_keeps_delimiters),
        ("H3 nests, fenced ## ignored", test_h3_stays_with_parent_and_fenced_h2_is_not_a_heading),
        ("expanded reply is cleaned and re-headed", test_clean_expanded_section),
        ("expansion reaches the target", test_expansion_reaches_the_target),
        ("compliant draft is left alone", test_expansion_stops_when_target_met),
        ("thinnest section is expanded first", test_expansion_picks_the_thinnest_section_first),
        ("a refusing writer is bounded", test_writer_that_will_not_grow_is_bounded),
        ("runaway reply is discarded", test_runaway_reply_is_discarded),
        ("draft with no sections is untouched", test_no_sections_returns_draft_unchanged),
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
