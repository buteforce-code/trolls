"""Per-role model routing tests.

Routing is pure env configuration, which is the failure mode this file exists for:
`OPENAI_MODEL` going missing once already demoted the whole swarm to a model that
could not clear the length gate. So the tests that matter here are the negative
ones — an unconfigured env must resolve to the legacy single model, a role must
never silently inherit a cheap default, and a missing API key must fail by name at
startup rather than eight stages into a run.

`swarm/llm.py` imports only os/typing at module level, so this needs neither ADK
nor litellm installed — every assertion below is about spec resolution, not about
building a live client.

    python tests/test_llm_routing.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm import llm  # noqa: E402
from swarm import telemetry as tm  # noqa: E402

# Every env var that can steer resolution. Cleared before each case so a value
# left in the developer's real .env cannot make a test pass or fail by accident.
_OWNED_VARS = (
    "LLM_MODEL_DEFAULT", "LLM_PROVIDER", "OPENAI_MODEL", "OPENAI_API_KEY",
    "OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_AI_API_KEY",
    "ADK_GEMINI_MODEL", "OPENAI_MAX_TOKENS",
) + tuple(f"LLM_MODEL_{role.upper()}" for role in llm.ROLES)


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


def _env(**overrides: str) -> None:
    """Reset every routing var, then apply the overrides for this case."""
    for name in _OWNED_VARS:
        os.environ.pop(name, None)
    for name, value in overrides.items():
        os.environ[name] = value
    llm.reset_cache()


class _FakeLiteLlm:
    """Stands in for ADK's LiteLlm, which holds its spec on `.model`."""

    def __init__(self, model: str) -> None:
        self.model = model


class _FakeAgent:
    def __init__(self, model: object) -> None:
        self.model = model


def test_unconfigured_env_uses_the_legacy_single_model() -> int:
    failures = 0
    _env(OPENAI_API_KEY="sk-test")
    for role in llm.ROLES:
        if llm.spec_for(role) is not None:
            _fail(f"role '{role}' claimed a routed spec with no LLM_MODEL_* set")
            failures += 1
    if llm.resolved_spec("writer") != "openai/gpt-5.4":
        _fail(f"legacy default drifted: {llm.resolved_spec('writer')}")
        failures += 1
    if llm.active_model_name("writer") != "gpt-5.4":
        _fail(f"legacy bare name wrong: {llm.active_model_name('writer')}")
        failures += 1
    return failures


def test_legacy_openai_model_var_still_steers_every_role() -> int:
    failures = 0
    _env(OPENAI_API_KEY="sk-test", OPENAI_MODEL="gpt-4.1")
    for role in llm.ROLES:
        if llm.resolved_spec(role) != "openai/gpt-4.1":
            _fail(f"role '{role}' ignored OPENAI_MODEL: {llm.resolved_spec(role)}")
            failures += 1
    return failures


def test_shared_default_applies_to_every_role() -> int:
    failures = 0
    _env(OPENROUTER_API_KEY="sk-or-test",
         LLM_MODEL_DEFAULT="openrouter/anthropic/claude-sonnet-4.5")
    for role in llm.ROLES:
        if llm.resolved_spec(role) != "openrouter/anthropic/claude-sonnet-4.5":
            _fail(f"role '{role}' missed LLM_MODEL_DEFAULT: {llm.resolved_spec(role)}")
            failures += 1
    return failures


def test_per_role_override_beats_the_shared_default() -> int:
    failures = 0
    _env(OPENAI_API_KEY="sk-test", OPENROUTER_API_KEY="sk-or-test",
         LLM_MODEL_DEFAULT="openrouter/google/gemini-2.5-flash",
         LLM_MODEL_WRITER="openai/gpt-5.4")
    if llm.resolved_spec("writer") != "openai/gpt-5.4":
        _fail(f"writer override lost: {llm.resolved_spec('writer')}")
        failures += 1
    if llm.resolved_spec("schema") != "openrouter/google/gemini-2.5-flash":
        _fail(f"schema should take the default: {llm.resolved_spec('schema')}")
        failures += 1
    # The whole point of routing: two roles, two providers, one run.
    if llm.resolved_spec("writer") == llm.resolved_spec("schema"):
        _fail("writer and schema collapsed to one model despite a split config")
        failures += 1
    return failures


def test_bare_model_name_is_treated_as_openai() -> int:
    failures = 0
    _env(OPENAI_API_KEY="sk-test", LLM_MODEL_WRITER="gpt-5.4")
    if llm.resolved_spec("writer") != "openai/gpt-5.4":
        _fail(f"bare name not qualified: {llm.resolved_spec('writer')}")
        failures += 1
    return failures


def test_missing_provider_key_fails_by_name() -> int:
    failures = 0
    # OpenAI key present, OpenRouter key absent — the routed role must still fail.
    _env(OPENAI_API_KEY="sk-test", LLM_MODEL_SOCIAL="openrouter/x-ai/grok-4")
    try:
        llm.make_text_model("social")
        _fail("routed to OpenRouter with no OPENROUTER_API_KEY and did not raise")
        failures += 1
    except RuntimeError as exc:
        if "OPENROUTER_API_KEY" not in str(exc):
            _fail(f"error did not name the missing var: {exc}")
            failures += 1
    except Exception as exc:  # ImportError would mean the key check ran too late
        _fail(f"expected RuntimeError naming the var, got {type(exc).__name__}: {exc}")
        failures += 1
    return failures


def test_unsupported_provider_is_rejected() -> int:
    failures = 0
    _env(OPENAI_API_KEY="sk-test", LLM_MODEL_LINKER="notaprovider/some-model")
    # 'notaprovider' is not a known prefix, so it is read as a bare OpenAI model
    # name — wrong, but it must not resolve to a *different vendor's* model.
    spec = llm.resolved_spec("linker")
    if not spec.startswith("openai/"):
        _fail(f"unknown prefix routed somewhere unexpected: {spec}")
        failures += 1
    try:
        llm._require_key("notaprovider/some-model")
        _fail("unsupported provider passed the key check")
        failures += 1
    except ValueError:
        pass
    return failures


def test_unknown_role_raises() -> int:
    failures = 0
    _env(OPENAI_API_KEY="sk-test")
    try:
        llm.make_text_model("wrtier")  # typo, as a call site would have it
        _fail("a misspelled role resolved instead of raising")
        failures += 1
    except ValueError:
        pass
    return failures


def test_bare_model_name_strips_multi_segment_specs() -> int:
    failures = 0
    cases = {
        "openrouter/anthropic/claude-sonnet-4.5": "claude-sonnet-4.5",
        "openai/gpt-5.4": "gpt-5.4",
        "gpt-5.4": "gpt-5.4",
        "gemini/gemini-2.5-flash": "gemini-2.5-flash",
    }
    for spec, expected in cases.items():
        if llm.bare_model_name(spec) != expected:
            _fail(f"{spec} → {llm.bare_model_name(spec)}, expected {expected}")
            failures += 1
    return failures


def test_model_name_read_off_the_agent() -> int:
    failures = 0
    _env(OPENAI_API_KEY="sk-test")
    # LiteLlm-shaped: the routed model must win over the env default.
    agent = _FakeAgent(_FakeLiteLlm("openrouter/google/gemini-2.5-flash"))
    if llm.model_name_of(agent) != "gemini-2.5-flash":
        _fail(f"LiteLlm-shaped agent misread: {llm.model_name_of(agent)}")
        failures += 1
    # Native-Gemini shape: a plain string.
    if llm.model_name_of(_FakeAgent("gemini-2.0-flash")) != "gemini-2.0-flash":
        _fail("string-model agent misread")
        failures += 1
    # Unexpected shape falls back to the env rather than crashing a priced run.
    if llm.model_name_of(_FakeAgent(None)) != "gpt-5.4":
        _fail(f"fallback wrong: {llm.model_name_of(_FakeAgent(None))}")
        failures += 1
    return failures


def test_routed_model_is_priced_by_telemetry() -> int:
    """The routing/telemetry seam: a 3-segment spec must still find its price."""
    failures = 0
    priced = tm.price_for("openrouter/openai/gpt-4o-mini")
    if priced != (0.15, 0.60):
        _fail(f"routed spec did not price off the bare name: {priced}")
        failures += 1
    # And a model nobody has priced must stay visible as unpriced, not guessed.
    if tm.price_for("openrouter/some-vendor/unknown-model") != (0.0, 0.0):
        _fail("an unknown routed model was silently assigned a price")
        failures += 1
    return failures


def test_routing_label_collapses_when_uniform() -> int:
    failures = 0
    _env(OPENAI_API_KEY="sk-test")
    label = llm.routing_label()
    if not label.startswith("all=openai/gpt-5.4"):
        _fail(f"uniform routing should collapse to one entry: {label}")
        failures += 1

    _env(OPENAI_API_KEY="sk-test", OPENROUTER_API_KEY="sk-or-test",
         LLM_MODEL_DEFAULT="openrouter/google/gemini-2.5-flash",
         LLM_MODEL_WRITER="openai/gpt-5.4")
    label = llm.routing_label()
    if "writer" not in label or "openai/gpt-5.4" not in label:
        _fail(f"split routing must name the writer's model: {label}")
        failures += 1
    if "gemini-2.5-flash" not in label:
        _fail(f"split routing must name the shared model: {label}")
        failures += 1
    return failures


def main() -> int:
    tests = [
        ("unconfigured env uses legacy model", test_unconfigured_env_uses_the_legacy_single_model),
        ("legacy OPENAI_MODEL steers all roles", test_legacy_openai_model_var_still_steers_every_role),
        ("shared default applies to all roles", test_shared_default_applies_to_every_role),
        ("per-role override wins", test_per_role_override_beats_the_shared_default),
        ("bare name treated as openai", test_bare_model_name_is_treated_as_openai),
        ("missing provider key fails by name", test_missing_provider_key_fails_by_name),
        ("unsupported provider rejected", test_unsupported_provider_is_rejected),
        ("unknown role raises", test_unknown_role_raises),
        ("bare name strips multi-segment", test_bare_model_name_strips_multi_segment_specs),
        ("model name read off agent", test_model_name_read_off_the_agent),
        ("routed model priced by telemetry", test_routed_model_is_priced_by_telemetry),
        ("routing label collapses", test_routing_label_collapses_when_uniform),
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
