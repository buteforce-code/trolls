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
LLM_MODEL_DEFAULT   fallback spec for every role   (unset → legacy path)
LLM_MODEL_<ROLE>    per-role spec override         (unset → LLM_MODEL_DEFAULT)
LLM_PROVIDER        openai | gemini                (default: openai)
OPENAI_MODEL        OpenAI chat model name         (default: gpt-5.4)
OPENAI_MAX_TOKENS   max output tokens              (default: 8192)
ADK_GEMINI_MODEL    Gemini model name              (default: gemini-2.0-flash)
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
# model, bills reasoning tokens against this same budget. A cap is not a target —
# unused headroom costs nothing, and hitting the cap truncates mid-post.
DEFAULT_MAX_TOKENS = 8192

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

# One model object per distinct spec, shared across the roles that resolve to it.
# The single-model version already shared one LiteLlm instance across all ten
# agents, so sharing is established as safe here; this only narrows it.
_MODEL_CACHE: dict[str, Any] = {}


def reset_cache() -> None:
    """Drop cached model objects. For tests that mutate the env between cases."""
    _MODEL_CACHE.clear()


def _provider() -> str:
    return os.environ.get("LLM_PROVIDER", "openai").strip().lower()


def _max_tokens() -> int:
    try:
        return int(os.environ.get("OPENAI_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)).strip())
    except ValueError:
        return DEFAULT_MAX_TOKENS


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


def _build(spec: str) -> Any:
    """LiteLlm instance for a fully qualified spec. Cached per spec."""
    if spec in _MODEL_CACHE:
        return _MODEL_CACHE[spec]

    _require_key(spec)
    # Imported lazily so a Gemini-only deploy doesn't need litellm installed.
    from google.adk.models.lite_llm import LiteLlm

    # LiteLLM resolves the provider from the prefix and reads the matching key
    # from the environment. Extra kwargs are forwarded to litellm.completion().
    model = LiteLlm(model=spec, max_tokens=_max_tokens())
    _MODEL_CACHE[spec] = model
    return model


def _legacy_model() -> Any:
    """The pre-routing single-model path, unchanged.

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
        return _build(f"openai/{model_name}")

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
        return _legacy_model()
    return _build(spec)


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
    unrouted case stays a short line.
    """
    table = routing_table()
    distinct = set(table.values())
    if len(distinct) == 1:
        return f"all={distinct.pop()} (max_tokens={_max_tokens()})"
    grouped: dict[str, list[str]] = {}
    for role, spec in table.items():
        grouped.setdefault(spec, []).append(role)
    parts = [f"{spec}←{'+'.join(roles)}" for spec, roles in sorted(grouped.items())]
    return f"{'; '.join(parts)} (max_tokens={_max_tokens()})"


def model_label() -> str:
    """Human-readable description of the active model, for logs."""
    return routing_label()
