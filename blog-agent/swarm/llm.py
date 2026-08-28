"""
Central LLM model factory for the Buteforce blog swarm.

Every ADK agent (research, audit, writer, humaniser, publisher, linker, schema,
social, imager, ideator) gets its text model from here, so switching providers or
re-routing one role is an env change rather than an edit across ten files.

Two layers, in priority order
-----------------------------
1. **Per-role routing** (preferred). ``LLM_MODEL_<ROLE>`` names a fully qualified
   LiteLLM spec for one role, e.g.::

       LLM_MODEL_WRITER=openai/gpt-5.4
       LLM_MODEL_SCHEMA=openrouter/google/gemini-2.5-flash
       LLM_MODEL_DEFAULT=openrouter/anthropic/claude-sonnet-4.5

   ``LLM_MODEL_DEFAULT`` covers every role without its own override. Roles can
   sit on different providers in the same run — the writer on OpenAI direct, the
   mechanical roles on OpenRouter — because the provider is read from the spec,
   not from a global switch.

2. **Legacy single-model path** (the default when no ``LLM_MODEL_*`` var is set).
   ``LLM_PROVIDER`` + ``OPENAI_MODEL`` / ``ADK_GEMINI_MODEL``, exactly as before.
   With nothing configured this module behaves identically to the single-model
   version it replaced — routing is opt-in, so a missing env var cannot silently
   demote the writer to a cheap model.

Providers
---------
- ``openai/<model>`` → ADK ``LiteLlm``. Needs ``OPENAI_API_KEY``.
- ``openrouter/<vendor>/<model>`` → ADK ``LiteLlm``. Needs ``OPENROUTER_API_KEY``.
  One balance across every vendor, at the cost of a per-top-up fee and a third
  party in the request path.
- ``gemini/<model>`` → ADK ``LiteLlm``. Needs ``GEMINI_API_KEY``.
- ``LLM_PROVIDER=gemini`` (legacy path only) → the bare model-name string, which
  ADK resolves natively via google-genai.

Env vars
--------
LLM_MODEL_DEFAULT      fallback spec for every role   (unset → legacy path)
LLM_MODEL_<ROLE>       per-role spec override         (unset → LLM_MODEL_DEFAULT)
LLM_PROVIDER           openai | gemini                (default: openai)
OPENAI_MODEL           OpenAI chat model name         (default: gpt-5.4)
LLM_MAX_TOKENS         max output tokens, all roles   (default: per role, see below)
LLM_MAX_TOKENS_<ROLE>  max output tokens, one role
OPENAI_MAX_TOKENS      legacy name for LLM_MAX_TOKENS, still honoured
LLM_FALLBACK_DEFAULT   comma-separated second-choice specs, every role  (default: none)
LLM_FALLBACK_<ROLE>    comma-separated second-choice specs, one role    (default: none)
ADK_GEMINI_MODEL       Gemini model name              (default: gemini-2.0-flash)

A note on ``LLM_PROVIDER``
-------------------------
It only steers the *legacy* path. The moment any ``LLM_MODEL_*`` var is set the
provider comes from that spec's prefix and LLM_PROVIDER is dead configuration —
which is why the 2026-08-27 writer failures arrived as an ``OpenrouterException``
from an environment whose .env still said ``LLM_PROVIDER=openai``. This module
never sets a base_url; LiteLLM derives the endpoint from the spec prefix alone.
"""
from __future__ import annotations

import os
from typing import Any

# gpt-4o was the default until 2026-08-02 and could not write long-form: it settled
# at ~650-760 words against the pipeline's 1,100-word floor and failed the length
# gate on every run. A bake-off on the real writer prompt (n=3) put gpt-4.1 astride
# the floor at 1069-1322 words and gpt-5.4 clear of it at 2135-2309, passing the GEO
# gate 3/3. The default matters: if OPENAI_MODEL goes missing from the environment,
# this is what the whole swarm silently falls back to.
DEFAULT_OPENAI_MODEL = "gpt-5.4"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

# A 1,400–2,000 word post is roughly 1,900–2,700 tokens before frontmatter and
# markdown. LiteLLM does not set max_tokens itself, so leaving it unset meant
# relying on provider defaults — a contributing factor in the truncated ~550-word
# drafts that shipped after the 2026-06-29 switch to gpt-4o.
#
# 8192 rather than 4096 since gpt-5.4: it writes longer posts (a 2,309-word draft
# measured 2,923 output tokens, already 71% of the old cap) and, as a reasoning
# model, bills reasoning tokens against this same budget. Hitting the cap truncates
# mid-post, so the writer keeps its headroom.
#
# "Unused headroom costs nothing" — which was the original reasoning here — turned
# out to be false on a prepaid provider. OpenRouter refuses a request outright when
# `max_tokens × the model's output rate` exceeds the remaining balance:
#
#   "You requested up to 8192 tokens, but can only afford 2074"  (402, 2026-08-27)
#
# So the cap is also the size of the reservation the provider checks the balance
# against, and a role that will only ever emit 400 tokens should not be asking to
# reserve 8192 of them. Hence the per-role override below: the writer keeps 8192,
# the mechanical roles can be told the truth about what they need.
DEFAULT_MAX_TOKENS = 8192

# Per-role caps for the roles whose output is structurally small. These are not
# guesses: schema emits one JSON-LD block, social a handful of posts, linker a
# list of anchors. Left unset a role inherits DEFAULT_MAX_TOKENS, so adding a role
# to ROLES without touching this table is safe.
ROLE_MAX_TOKENS: dict[str, int] = {
    "schema": 2048,
    "social": 2048,
    "linker": 2048,
    "imager": 1024,
    "ideator": 4096,
}

# Every role that reaches a model. Used to render the routing table at startup and
# to validate role names, so a typo in a call site fails loudly here instead of
# silently resolving to the default model.
ROLES: tuple[str, ...] = (
    "research", "audit", "writer", "humaniser", "publisher",
    "linker", "schema", "social", "imager", "ideator",
)

# Which env var holds the API key for each provider prefix. Checked before the
# call so a missing key is a startup error naming the variable, rather than a
# LiteLLM authentication failure eight stages into a run.
_PROVIDER_KEYS: dict[str, tuple[str, ...]] = {
    "openai":     ("OPENAI_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "gemini":     ("GEMINI_API_KEY", "GOOGLE_AI_API_KEY"),
}

# One model object per distinct (spec, max_tokens, fallbacks), shared across the
# roles that resolve to it. The single-model version already shared one LiteLlm
# instance across all ten agents, so sharing is established as safe here; this
# only narrows it. The cap is part of the key because per-role caps mean two roles
# on the same model are no longer interchangeable clients.
_MODEL_CACHE: dict[tuple[str, int, tuple[str, ...]], Any] = {}


def reset_cache() -> None:
    """Drop cached model objects. For tests that mutate the env between cases."""
    _MODEL_CACHE.clear()


def _provider() -> str:
    return os.environ.get("LLM_PROVIDER", "openai").strip().lower()


def _int_env(name: str) -> int | None:
    """Positive int from an env var, or None when unset/blank/unparseable.

    Unparseable is treated as unset rather than raising: a typo in a cap should
    cost the default, not the whole pipeline.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        print(f"[swarm] {name}={raw!r} is not an integer — ignoring it.", flush=True)
        return None
    return value if value > 0 else None


def max_tokens_for(role: str = "default") -> int:
    """Output-token cap for one role.

    Resolution order, most specific first:
      1. ``LLM_MAX_TOKENS_<ROLE>``   — one role, no deploy needed
      2. ``LLM_MAX_TOKENS``          — provider-neutral global
      3. ``OPENAI_MAX_TOKENS``       — the original name, still honoured
      4. ``ROLE_MAX_TOKENS[role]``   — the deliberate per-role default
      5. ``DEFAULT_MAX_TOKENS``

    ``OPENAI_MAX_TOKENS`` is kept because it is set in the live environment and in
    .env.example, but it is a misnomer: with per-role routing the cap applies to
    whichever provider the role resolved to, OpenAI or not. New configuration
    should use LLM_MAX_TOKENS.
    """
    explicit = _int_env(f"LLM_MAX_TOKENS_{role.strip().upper()}")
    if explicit:
        return explicit
    shared = _int_env("LLM_MAX_TOKENS") or _int_env("OPENAI_MAX_TOKENS")
    if shared:
        return shared
    return ROLE_MAX_TOKENS.get(role, DEFAULT_MAX_TOKENS)


def _max_tokens() -> int:
    """Back-compat shim for callers that predate per-role caps."""
    return max_tokens_for("default")


def fallback_specs_for(role: str) -> list[str]:
    """Second-choice models for a role, in order. Empty unless configured.

    ``LLM_FALLBACK_<ROLE>`` (or ``LLM_FALLBACK_DEFAULT``) takes a comma-separated
    list of specs in the same form as LLM_MODEL_*, e.g.::

        LLM_FALLBACK_WRITER=gemini/gemini-2.5-flash

    Passed straight to LiteLLM's own ``fallbacks`` kwarg, so the failover happens
    inside the client this module already builds — no second architecture, no
    rebuilding an ADK agent mid-run.

    **Deliberately empty by default.** A fallback is the right answer for a
    provider outage and the wrong one for a quality-critical role: the comment on
    DEFAULT_OPENAI_MODEL above records that gpt-4o could not clear the 1,100-word
    length gate at all, so silently demoting the writer buys a draft that fails a
    gate and costs a second call. Set it for the mechanical roles first; set it
    for the writer only against a model you have actually bake-tested.
    """
    raw = (
        os.environ.get(f"LLM_FALLBACK_{role.strip().upper()}", "").strip()
        or os.environ.get("LLM_FALLBACK_DEFAULT", "").strip()
    )
    if not raw:
        return []
    return [_qualify(part) for part in raw.split(",") if part.strip()]


def _role_env(role: str) -> str:
    return f"LLM_MODEL_{role.strip().upper()}"


def spec_for(role: str) -> str | None:
    """Fully qualified LiteLLM spec for a role, or None to use the legacy path.

    Returns None only when neither the role's own var nor LLM_MODEL_DEFAULT is
    set — that is the signal to fall through to LLM_PROVIDER/OPENAI_MODEL.
    """
    explicit = os.environ.get(_role_env(role), "").strip()
    if explicit:
        return _qualify(explicit)
    shared = os.environ.get("LLM_MODEL_DEFAULT", "").strip()
    if shared:
        return _qualify(shared)
    return None


def _qualify(spec: str) -> str:
    """Add the implied ``openai/`` prefix to a bare model name.

    ``gpt-5.4`` and ``openai/gpt-5.4`` mean the same thing, so both are accepted;
    anything already carrying a known provider prefix is left alone.
    """
    spec = spec.strip()
    head = spec.split("/", 1)[0].lower()
    if head in _PROVIDER_KEYS:
        return spec
    return f"openai/{spec}"


def _require_key(spec: str) -> None:
    provider = spec.split("/", 1)[0].lower()
    candidates = _PROVIDER_KEYS.get(provider)
    if not candidates:
        raise ValueError(
            f"Model spec '{spec}' names an unsupported provider '{provider}'. "
            f"Use one of: {', '.join(sorted(_PROVIDER_KEYS))}."
        )
    if not any(os.environ.get(name) for name in candidates):
        raise RuntimeError(
            f"Model spec '{spec}' needs {' or '.join(candidates)}, which is not set. "
            f"Add it to .env (or the Railway env) and retry."
        )


def _build(spec: str, role: str = "default") -> Any:
    """LiteLlm instance for a fully qualified spec.

    Cached on (spec, cap, fallbacks) rather than on the spec alone: two roles can
    now resolve to the same model with different caps, and returning the first
    role's client to the second would silently apply the wrong budget.
    """
    cap = max_tokens_for(role)
    fallbacks = fallback_specs_for(role)
    cache_key = (spec, cap, tuple(fallbacks))
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    _require_key(spec)
    for fallback in fallbacks:
        # Same check as the primary, and for the same reason: a fallback whose key
        # is missing is not a fallback, it is a second failure discovered during
        # the first one.
        _require_key(fallback)

    # Imported lazily so a Gemini-only deploy doesn't need litellm installed.
    from google.adk.models.lite_llm import LiteLlm

    # LiteLLM resolves the provider from the prefix and reads the matching key
    # from the environment. Extra kwargs are forwarded to litellm.completion(),
    # which is how `fallbacks` reaches litellm's own failover path.
    kwargs: dict[str, Any] = {"max_tokens": cap}
    if fallbacks:
        kwargs["fallbacks"] = fallbacks
    model = LiteLlm(model=spec, **kwargs)
    _MODEL_CACHE[cache_key] = model
    return model


def _legacy_model(role: str = "default") -> Any:
    """The pre-routing single-model path, unchanged apart from the per-role cap.

    Reached when no LLM_MODEL_* var is set, which is what keeps an unconfigured
    deploy byte-identical to the single-model behaviour.
    """
    provider = _provider()

    if provider == "gemini":
        return os.environ.get("ADK_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

    if provider == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set. "
                "Add it to .env (or the Railway env) and retry."
            )
        model_name = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        return _build(f"openai/{model_name}", role)

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. Use 'openai' or 'gemini'."
    )


def make_text_model(role: str = "default") -> Any:
    """Return the model object/string the ADK ``LlmAgent`` for ``role`` should use.

    For LiteLLM providers this is a ``LiteLlm`` instance; for the legacy native
    Gemini path it is a plain string. ``LlmAgent(model=...)`` accepts either form.

    ``role="default"`` keeps the no-argument call working for callers that have no
    role of their own.
    """
    if role != "default" and role not in ROLES:
        raise ValueError(f"Unknown model role '{role}'. Known roles: {', '.join(ROLES)}.")

    spec = spec_for(role)
    if spec is None:
        return _legacy_model(role)
    return _build(spec, role)


def resolved_spec(role: str = "default") -> str:
    """Fully qualified spec a role will actually run on, legacy path included."""
    spec = spec_for(role)
    if spec is not None:
        return spec
    if _provider() == "gemini":
        return f"gemini-native/{os.environ.get('ADK_GEMINI_MODEL', DEFAULT_GEMINI_MODEL)}"
    return f"openai/{os.environ.get('OPENAI_MODEL', DEFAULT_OPENAI_MODEL)}"


def bare_model_name(spec: str) -> str:
    """Last path segment of a spec, e.g. 'openrouter/openai/gpt-5.4' → 'gpt-5.4'.

    This is the form ``telemetry.price_for`` looks up.
    """
    name = (spec or "").strip()
    return name.rsplit("/", 1)[-1] if "/" in name else name


def active_model_name(role: str = "default") -> str:
    """Bare model name for a role, e.g. 'gpt-5.4'. Used by telemetry to price a call."""
    return bare_model_name(resolved_spec(role))


def model_name_of(agent: Any) -> str:
    """Bare model name an already-built agent is holding.

    Telemetry prices from this rather than from the env, because with per-role
    routing the env no longer says which model a given agent got — reading it
    back off the agent is the only way the cost line matches the call. Falls back
    to the default role if the agent shape is unexpected.
    """
    model = getattr(agent, "model", None)
    name = getattr(model, "model", None)
    if not name and isinstance(model, str):
        name = model
    if not name:
        return active_model_name()
    return bare_model_name(str(name))


def routing_table() -> dict[str, str]:
    """role → fully qualified spec, for every role."""
    return {role: resolved_spec(role) for role in ROLES}


def routing_label() -> str:
    """One-line summary of the active routing, for the startup log.

    Collapses to ``all=<spec>`` when every role shares a model, so the common
    unrouted case stays a short line. The cap is printed per group, because on a
    prepaid provider the cap is what the balance check is run against and a
    startup line that hides it hides half the reason a call gets refused.
    """
    table = routing_table()
    grouped: dict[str, list[str]] = {}
    for role, spec in table.items():
        grouped.setdefault(spec, []).append(role)

    if len(grouped) == 1:
        spec = next(iter(grouped))
        return f"all={spec} (max_tokens={max_tokens_for('writer')})"

    parts = []
    for spec, roles in sorted(grouped.items()):
        caps = sorted({max_tokens_for(r) for r in roles})
        cap = str(caps[0]) if len(caps) == 1 else f"{caps[0]}-{caps[-1]}"
        parts.append(f"{spec}←{'+'.join(roles)} @{cap}tok")
    return "; ".join(parts)


def model_label() -> str:
    """Human-readable description of the active model, for logs."""
    return routing_label()
