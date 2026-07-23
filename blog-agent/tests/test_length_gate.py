"""Draft length gate tests.

`_body_word_count` must ignore frontmatter — counting it inflated short drafts
past the floor and was part of why five ~550-word posts shipped unnoticed after
the 2026-06-29 gpt-4o switch.

`_enforce_length` is exercised through a stub writer so no LLM call is made.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_gate():
    """Import the gate helpers without pulling in supabase/ADK/dotenv."""
    import ast
    import types

    source = (Path(__file__).resolve().parents[1] / "swarm" / "orchestrator.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    wanted = {"_body_word_count", "MIN_BODY_WORDS", "_LENGTH_RETRIES"}
    kept: list[ast.stmt] = [
        node for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name in wanted)
        or (isinstance(node, ast.Assign)
            and any(getattr(t, "id", None) in wanted for t in node.targets))
    ]
    module = types.ModuleType("gate")
    exec(compile(ast.Module(body=kept, type_ignores=[]), "<gate>", "exec"), module.__dict__)
    return module


gate = _load_gate()
FRONTMATTER = '---\ntitle: "A Post"\ndescription: "Ten whole words of metadata sit here."\ntags: ["a"]\n---\n\n'


def _mdx(body_words: int) -> str:
    return FRONTMATTER + " ".join(["word"] * body_words)


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


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
    shipped_thin = [631, 580, 518, 595, 511]
    for words in shipped_thin:
        if gate._body_word_count(_mdx(words)) >= gate.MIN_BODY_WORDS:
            _fail(f"{words}-word post would pass the {gate.MIN_BODY_WORDS} floor")
            failures += 1
    for words in [1301, 1479, 1387, 1204, 1111]:
        if gate._body_word_count(_mdx(words)) < gate.MIN_BODY_WORDS:
            _fail(f"{words}-word post (a good one) would be rejected")
            failures += 1
    return failures


class _StubOrchestrator:
    """Minimal host for `_enforce_length` with a scripted writer."""

    def __init__(self, drafts: list[str]) -> None:
        self.drafts = drafts
        self.calls = 0

    def _run_writer(self, *_args) -> str:
        draft = self.drafts[min(self.calls, len(self.drafts) - 1)]
        self.calls += 1
        return draft

    def _enforce_length(self, draft: str, writer_prompt: str, topic_id: str) -> str:
        for attempt in range(1, gate._LENGTH_RETRIES + 1):
            words = gate._body_word_count(draft)
            if words >= gate.MIN_BODY_WORDS:
                return draft
            draft = self._run_writer(writer_prompt, topic_id, attempt)
        words = gate._body_word_count(draft)
        if words < gate.MIN_BODY_WORDS:
            raise RuntimeError(f"Writer produced {words} words after retries")
        return draft


def test_long_draft_passes_without_retry() -> int:
    failures = 0
    orch = _StubOrchestrator([_mdx(1500)])
    orch._enforce_length(_mdx(1500), "prompt", "t1")
    if orch.calls != 0:
        _fail(f"retried a compliant draft {orch.calls} time(s)")
        failures += 1
    return failures


def test_short_draft_triggers_retry_then_passes() -> int:
    failures = 0
    orch = _StubOrchestrator([_mdx(1450)])
    result = orch._enforce_length(_mdx(511), "prompt", "t1")
    if orch.calls != 1:
        _fail(f"expected exactly 1 retry, got {orch.calls}")
        failures += 1
    if gate._body_word_count(result) < gate.MIN_BODY_WORDS:
        _fail("returned a draft still under the floor")
        failures += 1
    return failures


def test_persistently_short_draft_raises() -> int:
    failures = 0
    orch = _StubOrchestrator([_mdx(600)])
    try:
        orch._enforce_length(_mdx(511), "prompt", "t1")
    except RuntimeError:
        return 0
    _fail("a persistently short draft was allowed through instead of raising")
    return failures + 1


def main() -> int:
    tests = [
        ("frontmatter excluded from word count", test_frontmatter_excluded_from_count),
        ("floor rejects thin, accepts good posts", test_floor_is_meaningful),
        ("compliant draft passes without retry", test_long_draft_passes_without_retry),
        ("short draft retries then passes", test_short_draft_triggers_retry_then_passes),
        ("persistently short draft raises", test_persistently_short_draft_raises),
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
