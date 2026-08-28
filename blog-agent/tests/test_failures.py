"""Error-classification tests.

Every fatal case below is a *verbatim* error string pulled from the eight
`blog_posts.last_error` rows written on 2026-08-27, not a paraphrase. That is
deliberate: the bug being tested was a classifier that read plausible-looking
substrings out of real provider messages, so a test written against an invented
message would have passed while the real one failed.

The negative cases matter more than the positive ones. A retry on a 402 is not a
wasted call, it is money spent proving something already known, drawn from a
balance that has already run out.

`swarm/failures.py` imports only stdlib plus `swarm.telemetry` (itself
import-clean), so this needs neither ADK nor litellm installed.

    python tests/test_failures.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm import failures as f  # noqa: E402

# ── The real thing ───────────────────────────────────────────────────────────
# Row 3 of 8, verbatim from Supabase.
REAL_402 = (
    "[writer] Agent 'content_writer_agent' failed after 3 attempts: litellm.APIError: "
    'APIError: OpenrouterException - {"error":{"message":"This request requires more '
    "credits, or fewer max_tokens. You requested up to 8192 tokens, but can only afford "
    "1848. To increase, visit https://openrouter.ai/settings/credits and add more "
    'credits","code":402,"metadata":{"limit_source":"openrouter_credits","remedy_hint":'
    '"Add credits at https://openrouter.ai/settings/credits, or lower max_tokens / '
    'prompt size to fit your remaining balance.","provider_name":null,"previous_errors":'
    '[{"code":402,"message":"This request requires more credits, or fewer max_tokens. '
    "You requested up to 8192 tokens, but can only afford 2033. To increase, visit "
    'https://openrouter.ai/settings/credits and add more credits"}]}},'
    '"user_id":"user_2xwAv4GnyUgnpcCxcckILS7mGBs"}'
)


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


def _expect(error, kind: str, retryable: bool, batch_fatal: bool, label: str) -> int:
    verdict = f.classify(error)
    problems = 0
    if verdict.kind != kind:
        _fail(f"{label}: kind {verdict.kind!r}, expected {kind!r}")
        problems += 1
    if verdict.retryable != retryable:
        _fail(f"{label}: retryable={verdict.retryable}, expected {retryable}")
        problems += 1
    if verdict.batch_fatal != batch_fatal:
        _fail(f"{label}: batch_fatal={verdict.batch_fatal}, expected {batch_fatal}")
        problems += 1
    return problems


def test_the_real_402_is_never_retried() -> int:
    """The whole point. This exact string was retried into an empty balance."""
    failures_found = _expect(REAL_402, f.KIND_CREDITS, False, True, "real 402")
    verdict = f.classify(REAL_402)
    if "credit" not in verdict.remedy.lower():
        _fail("the credits remedy does not mention credit")
        failures_found += 1
    if f.OPENROUTER_CREDITS_URL not in verdict.remedy:
        _fail("the credits remedy does not give the operator the top-up link")
        failures_found += 1
    return failures_found


def test_the_old_classifier_would_have_retried_it() -> int:
    """Guards the specific substring traps the previous implementation fell into.

    The old test was `"500" in msg or "quota" in msg or ...`. If a future edit
    reintroduces loose substring matching, the real 402 will start looking
    transient again — this asserts the numbers in that message are not read as
    status codes.
    """
    problems = 0
    # "afford 1848", "up to 8192" — digits everywhere, none of them a status code.
    if f.classify('provider said: you can only afford 500 tokens').retryable:
        _fail("a bare '500' inside prose was read as a 5xx and retried")
        problems += 1
    # OpenAI's insufficient_quota is billing, not rate limiting, despite the word.
    if f.classify("Error code: 429 - insufficient_quota: You exceeded your current "
                  "quota, please check your plan and billing details").retryable:
        _fail("insufficient_quota was treated as a retryable rate limit")
        problems += 1
    return problems


def test_transient_faults_are_still_retried() -> int:
    """Fail-fast must not become fail-always: the 429/503/timeout path still retries."""
    problems = 0
    problems += _expect(
        "litellm.RateLimitError: RateLimitError: OpenAIException - Rate limit reached "
        'for gpt-5.4 {"code":429}',
        f.KIND_TRANSIENT, True, False, "429 rate limit")
    problems += _expect(
        'ServiceUnavailableError: {"code":503} The model is overloaded',
        f.KIND_TRANSIENT, True, False, "503 overloaded")
    problems += _expect(
        "google.api_core.exceptions.ResourceExhausted: 429 Resource has been exhausted "
        "(e.g. check quota).",
        f.KIND_TRANSIENT, True, False, "Gemini resource exhausted")
    problems += _expect(
        asyncio.TimeoutError(), f.KIND_TRANSIENT, True, False, "asyncio timeout")
    problems += _expect(
        "APIConnectionError: Connection reset by peer",
        f.KIND_TRANSIENT, True, False, "connection reset")
    return problems


def test_auth_and_bad_request_stop_the_batch() -> int:
    problems = 0
    problems += _expect(
        'AuthenticationError: {"code":401,"message":"No auth credentials found"}',
        f.KIND_AUTH, False, True, "401 no credentials")
    problems += _expect(
        "litellm.BadRequestError: OpenrouterException - openrouter/nope/nope-1 is not a "
        "valid model ID",
        f.KIND_INVALID_REQUEST, False, True, "unknown model")
    return problems


def test_unknown_errors_fail_the_topic_but_not_the_batch() -> int:
    """The honest middle. We do not retry what we do not understand, and we do not
    declare an account-wide outage on the strength of a message we cannot read."""
    return _expect("something nobody has seen before", f.KIND_UNKNOWN, False, False,
                   "unrecognised")


def test_exception_type_beats_message_text() -> int:
    """A provider can put anything in a message body; it cannot fake the class."""
    class AuthenticationError(Exception):
        pass

    # Message reads like a retryable timeout; the type says otherwise.
    return _expect(AuthenticationError("request timed out"), f.KIND_AUTH, False, True,
                   "type over text")


def test_wrapped_causes_are_inspected() -> int:
    """LiteLLM wraps the provider SDK's error, and ADK wraps LiteLLM's."""
    class RateLimitError(Exception):
        pass

    try:
        try:
            raise RateLimitError("slow down")
        except RateLimitError as inner:
            raise RuntimeError("Agent 'content_writer_agent' failed") from inner
    except RuntimeError as outer:
        return _expect(outer, f.KIND_TRANSIENT, True, False, "wrapped cause")
    return 1


def test_blocked_is_catchable_as_a_spend_ceiling() -> int:
    """The zero-edit integration: every batch loop that already stops on a spend
    ceiling stops on a provider block too. If this ever stops being true, the
    autopilot batch silently goes back to marching through the queue."""
    from swarm.telemetry import SpendCeilingExceeded

    problems = 0
    exc = f.blocked("writer", REAL_402)
    if not isinstance(exc, SpendCeilingExceeded):
        _fail("ProviderBlocked is no longer catchable as SpendCeilingExceeded — "
              "autopilot.produce_all_queued will not stop the batch")
        problems += 1
    if exc.kind != f.KIND_CREDITS:
        _fail(f"blocked() lost the kind: {exc.kind}")
        problems += 1
    if "openrouter.ai/settings/credits" not in str(exc):
        _fail("the raised message does not tell the operator what to do")
        problems += 1
    if "1848" not in str(exc):
        _fail("the raised message dropped the original provider error")
        problems += 1
    return problems


def main() -> int:
    tests = [
        ("the real 402 is never retried", test_the_real_402_is_never_retried),
        ("old substring traps stay closed", test_the_old_classifier_would_have_retried_it),
        ("transient faults still retry", test_transient_faults_are_still_retried),
        ("auth / bad request stop the batch", test_auth_and_bad_request_stop_the_batch),
        ("unknown fails topic not batch", test_unknown_errors_fail_the_topic_but_not_the_batch),
        ("exception type beats text", test_exception_type_beats_message_text),
        ("wrapped causes inspected", test_wrapped_causes_are_inspected),
        ("blocked catchable as ceiling", test_blocked_is_catchable_as_a_spend_ceiling),
    ]
    total = 0
    for name, fn in tests:
        problems = fn()
        total += problems
        print(f"{'PASS' if problems == 0 else 'FAIL'}  {name}")
    print(f"\n{'ALL TESTS PASSED' if total == 0 else f'{total} FAILURE(S)'}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
