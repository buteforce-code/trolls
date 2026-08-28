"""Failure classification — which errors are worth retrying, and which are not.

Why this exists
---------------
On 2026-08-27 eight topics died in a row at the writer, every one of them on the
same OpenRouter 402:

    "This request requires more credits, or fewer max_tokens. You requested up
     to 8192 tokens, but can only afford 2074."

Nothing in the code was broken. The account was out of money — OpenRouter's
`total_usage` had passed `total_credits` — and every call sent after that moment
was doomed before it left the process. The affordable-token figure in the eight
stored errors declines monotonically (2074 → 1957 → 1848 → … → 1248), which is
the balance draining while the batch marched on.

Two separate defects turned one billing event into eight dead topics:

1. **The retry classifier only recognised transient faults, by substring**
   ("429", "503", "overloaded", "quota"). A 402 matched none of them, so the
   loop fell straight through to `break` — and then raised
   ``failed after 3 attempts`` anyway, because the message interpolated the
   *budget* rather than the attempts actually made. The one line an operator
   reads first misreported the mechanism.

2. **The batch loops treat every failure as a per-topic problem** and move to
   the next topic. For a transient fault that is correct. For "the account has
   no money" it is eight identical failures and eight research digests paid for
   and thrown away.

So classification lives here, in one place, and answers two questions:

    can this be retried?          → ``Verdict.retryable``
    must the whole batch stop?    → ``Verdict.batch_fatal``

Like ``swarm/geo.py`` and ``swarm/telemetry.py`` this module is deliberately
**import-clean** — stdlib only, no ADK, no litellm, no supabase — so it is
directly testable against the real stored error strings:

    python tests/test_failures.py
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from swarm.telemetry import SpendCeilingExceeded

# ── Kinds ────────────────────────────────────────────────────────────────────
# Small and closed, like telemetry's event kinds: each one maps to a different
# operator action, and a kind nobody can act on is not worth having.
KIND_TRANSIENT = "transient"          # retry: capacity, rate limit, timeout, reset
KIND_CREDITS = "credits"              # stop:  the account is out of money
KIND_AUTH = "auth"                    # stop:  the key is missing, wrong or revoked
KIND_INVALID_REQUEST = "invalid_request"  # stop:  we asked for something impossible
KIND_UNKNOWN = "unknown"              # neither: surface it, don't guess

# What the operator does about each kind. These strings reach a human — in the
# log, in `blog_posts.last_error`, and (parsed) in the dashboard banner — so they
# name the next action, not the diagnosis.
REMEDIES: dict[str, str] = {
    KIND_CREDITS: (
        "The LLM account is out of credit. Top it up "
        "(OpenRouter: https://openrouter.ai/settings/credits) or point the roles at a "
        "provider that still has balance. No retry can fix this."
    ),
    KIND_AUTH: (
        "The provider rejected the API key. Check the key env var for the routed "
        "provider (OPENROUTER_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY) and that the "
        "key has not been revoked or rate-scoped. No retry can fix this."
    ),
    KIND_INVALID_REQUEST: (
        "The provider rejected the request itself — usually an unknown model name or a "
        "prompt over the context window. Check the LLM_MODEL_* routing and the prompt "
        "size. No retry can fix this."
    ),
    KIND_TRANSIENT: "Transient provider fault. Retrying with backoff.",
    KIND_UNKNOWN: "Unrecognised provider error — see the full text below.",
}

# The credit top-up page, quoted verbatim by OpenRouter's own remedy_hint. Kept
# as a constant because the dashboard renders it as a link and the two must agree.
OPENROUTER_CREDITS_URL = "https://openrouter.ai/settings/credits"


class ProviderBlocked(SpendCeilingExceeded):
    """The provider refused the call for a reason the next call will hit too.

    Subclassing ``SpendCeilingExceeded`` is deliberate, not laziness. That is
    already the one exception the batch loops treat as "stop the batch rather
    than fail this topic" — ``autopilot.produce_all_queued`` catches it before
    its generic handler and breaks, and ``orchestrator.recorded_run`` closes the
    run against it. Every reason this is raised (no credit, bad key, malformed
    request) is exactly as true for the ninth topic as it was for the first, so
    the correct behaviour is byte-for-byte the behaviour a spend ceiling already
    gets. A brand-new exception type would have needed the same handling added
    to every loop, and the loop that got missed would be the one that burned the
    backlog.

    Carries the classification so the caller can log it and the dashboard can
    render the right next step instead of "a stage crashed".
    """

    def __init__(self, message: str, kind: str = KIND_UNKNOWN, remedy: str = "") -> None:
        super().__init__(message)
        self.kind = kind
        self.remedy = remedy or REMEDIES.get(kind, "")


@dataclass(frozen=True)
class Verdict:
    """What to do about one exception."""
    kind: str
    retryable: bool
    batch_fatal: bool
    reason: str

    @property
    def remedy(self) -> str:
        return REMEDIES.get(self.kind, "")


# ── Signals ──────────────────────────────────────────────────────────────────
# Exception *type names* first, because they are the only signal a provider
# cannot accidentally put in a message body. LiteLLM maps every provider onto
# these OpenAI-shaped classes, so one table covers OpenAI, OpenRouter and Gemini.
_TYPE_KINDS: dict[str, str] = {
    "authenticationerror":       KIND_AUTH,
    "permissiondeniederror":     KIND_AUTH,
    "badrequesterror":           KIND_INVALID_REQUEST,
    "notfounderror":             KIND_INVALID_REQUEST,
    "unprocessableentityerror":  KIND_INVALID_REQUEST,
    "contextwindowexceedederror": KIND_INVALID_REQUEST,
    "unsupportedparamserror":    KIND_INVALID_REQUEST,
    "ratelimiterror":            KIND_TRANSIENT,
    "timeout":                   KIND_TRANSIENT,
    "timeouterror":              KIND_TRANSIENT,
    "apiconnectionerror":        KIND_TRANSIENT,
    "serviceunavailableerror":   KIND_TRANSIENT,
    "internalservererror":       KIND_TRANSIENT,
    # litellm.APIError is the catch-all it maps anything unrecognised onto — the
    # 402 arrived as one — so it is deliberately absent. It tells us nothing.
}

# HTTP status codes, read only from *structured* positions. The old classifier
# tested `"500" in msg`, which a 402 body mentioning "1,500 tokens" would satisfy;
# a status code has to look like a status code to count as one.
_CODE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'"code"\s*:\s*(\d{3})\b'),                      # OpenRouter/OpenAI JSON body
    re.compile(r'\bstatus[_ ]?code\s*[:=]\s*(\d{3})\b', re.I),  # litellm / httpx
    re.compile(r'\berror code\s*[:=]?\s*(\d{3})\b', re.I),      # openai-python
    re.compile(r'\bHTTP\s*(\d{3})\b', re.I),
)

_CODE_KINDS: dict[int, str] = {
    400: KIND_INVALID_REQUEST,
    401: KIND_AUTH,
    403: KIND_AUTH,
    402: KIND_CREDITS,
    404: KIND_INVALID_REQUEST,
    422: KIND_INVALID_REQUEST,
    408: KIND_TRANSIENT,
    409: KIND_TRANSIENT,
    429: KIND_TRANSIENT,
    500: KIND_TRANSIENT,
    502: KIND_TRANSIENT,
    503: KIND_TRANSIENT,
    504: KIND_TRANSIENT,
    529: KIND_TRANSIENT,  # Anthropic "overloaded"
}

# Phrase tables. Order of *evaluation* matters more than the tables themselves —
# see `_kind_from_text`. Every phrase here was taken from a real provider error,
# not invented.
_CREDIT_PHRASES: tuple[str, ...] = (
    "requires more credits",
    "add more credits",
    "openrouter_credits",
    "insufficient credits",
    "insufficient_quota",              # OpenAI: a *billing* stop, not a rate limit
    "exceeded your current quota",     # OpenAI, same event, prose form
    "credit balance is too low",       # Anthropic
    "payment required",
    "purchase more credits",
    "negative balance",
)
# Note what is NOT in that list: the bare word "billing". OpenAI's genuine,
# retryable rate-limit message ends "Please add a payment method to your account
# to increase your rate limit", and its 429 prose mentions billing details too.
# A phrase that appears in both the fatal and the transient message is worse than
# no phrase at all, because it turns a retryable fault into a stopped batch.

_AUTH_PHRASES: tuple[str, ...] = (
    "invalid api key",
    "incorrect api key",
    "api key not valid",
    "no auth credentials",
    "unauthorized",
    "authentication",
    "permission denied",
    "api_key_invalid",
    "invalid_api_key",
)

_INVALID_PHRASES: tuple[str, ...] = (
    "invalid_request_error",
    "is not a valid model",
    "model_not_found",
    "does not exist or you do not have access",
    "maximum context length",
    "context length exceeded",
    "context_length_exceeded",
    "unsupported parameter",
)

_TRANSIENT_PHRASES: tuple[str, ...] = (
    "rate limit",
    "ratelimit",
    "resource exhausted",       # Gemini's rate limit, prose form
    "resource_exhausted",
    "overloaded",
    "service unavailable",
    "temporarily unavailable",
    "high demand",
    "timed out",
    "timeout",
    "connection reset",
    "connection aborted",
    "apiconnection",
    "remote end closed",
    "please try again",
)


def _text(error: BaseException | str | None) -> str:
    return ("" if error is None else str(error)).lower()


def _type_names(error: BaseException | str | None) -> list[str]:
    """Type names of the exception and everything it was raised from.

    LiteLLM wraps provider SDK errors, and ADK wraps LiteLLM's, so the class that
    actually knows what happened is often two `__cause__` links down.
    """
    names: list[str] = []
    seen: set[int] = set()
    node = error if isinstance(error, BaseException) else None
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        names.append(type(node).__name__.lower())
        node = node.__cause__ or node.__context__
    return names


def _status_code(text: str) -> int | None:
    """First status-code-shaped number in the message, or None."""
    for pattern in _CODE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    return None


def _kind_from_text(text: str) -> str:
    """Kind implied by the message body.

    The evaluation order is the whole point. OpenAI's ``insufficient_quota`` is a
    billing stop that contains the word "quota", and Gemini's retryable rate limit
    is prose containing "quota" too. The old classifier saw "quota" and retried
    both. Fatal families are therefore tested *before* the transient phrases, and
    the fatal phrases are specific where the transient ones are loose.
    """
    if any(phrase in text for phrase in _CREDIT_PHRASES):
        return KIND_CREDITS
    if any(phrase in text for phrase in _AUTH_PHRASES):
        return KIND_AUTH
    if any(phrase in text for phrase in _INVALID_PHRASES):
        return KIND_INVALID_REQUEST
    if any(phrase in text for phrase in _TRANSIENT_PHRASES):
        return KIND_TRANSIENT
    # Bare "quota" with none of the above: Gemini's shape, treat as rate limiting.
    if "quota" in text:
        return KIND_TRANSIENT
    return KIND_UNKNOWN


def classify(error: BaseException | str | None) -> Verdict:
    """Decide what to do about one failure. Never raises."""
    if isinstance(error, asyncio.TimeoutError):
        # Stringifies to '' — decided by type, or it would land in UNKNOWN and
        # the call timeout would stop being retried at all.
        return Verdict(KIND_TRANSIENT, retryable=True, batch_fatal=False,
                       reason="the call timed out")

    text = _text(error)

    # 1. An exhausted balance, ahead of every other signal — including the
    #    exception class and the status code, which is the whole reason this check
    #    is first. OpenAI reports a spent balance as HTTP 429 with a RateLimitError,
    #    the exact shape of a genuine rate limit; only the body's
    #    `insufficient_quota` tells them apart. Classify by code or by type there
    #    and the pipeline sits in a 20/40/60-second backoff waiting for money to
    #    reappear. Every phrase in _CREDIT_PHRASES is specific enough to say this
    #    on its own.
    if any(phrase in text for phrase in _CREDIT_PHRASES):
        return _verdict(KIND_CREDITS, "the provider says the account is out of credit")

    # 2. Exception type, innermost first. A provider cannot fake this.
    for name in _type_names(error):
        kind = _TYPE_KINDS.get(name)
        if kind:
            return _verdict(kind, f"{name} from the provider")

    # 3. Status code, read only from a structured position.
    code = _status_code(text)
    if code is not None:
        kind = _CODE_KINDS.get(code)
        if kind:
            return _verdict(kind, f"provider returned HTTP {code}")

    # 4. Message body, remaining fatal families first.
    kind = _kind_from_text(text)
    if kind != KIND_UNKNOWN:
        return _verdict(kind, "matched on the provider's error text")

    # Unrecognised. Not retried (we have no reason to think a repeat differs) and
    # not batch-fatal (we have no reason to think the next topic shares it) — the
    # honest position is to fail this topic loudly and let the operator read it.
    return Verdict(KIND_UNKNOWN, retryable=False, batch_fatal=False,
                   reason="unrecognised provider error")


def _verdict(kind: str, reason: str) -> Verdict:
    transient = kind == KIND_TRANSIENT
    return Verdict(
        kind=kind,
        retryable=transient,
        # Everything non-transient that we *did* recognise is a property of the
        # account or the configuration, not of this topic. The next topic hits it
        # too, so the batch stops.
        batch_fatal=kind in (KIND_CREDITS, KIND_AUTH, KIND_INVALID_REQUEST),
        reason=reason,
    )


def is_retryable(error: BaseException | str | None) -> bool:
    return classify(error).retryable


def blocked(where: str, error: BaseException | str, verdict: Verdict | None = None) -> ProviderBlocked:
    """Build the ProviderBlocked to raise for a batch-fatal failure.

    The message leads with the remedy, because it is written straight into
    ``blog_posts.last_error`` and read by someone asking "why did everything
    stop", not by someone reading a stack trace.
    """
    verdict = verdict or classify(error)
    return ProviderBlocked(
        f"[{verdict.kind}] {verdict.remedy} "
        f"(stage: {where}; {verdict.reason}) — original error: {error}",
        kind=verdict.kind,
        remedy=verdict.remedy,
    )
