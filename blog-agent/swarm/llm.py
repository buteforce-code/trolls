"""
Central LLM model factory for the Buteforce blog swarm.

Every ADK agent (research, writer, humaniser, publisher, ideator, linker,
schema, social) gets its text model from here, so switching providers is a
single env change rather than an edit across eight files.

Providers
---------
- ``openai`` (default) → returns an ADK ``LiteLlm`` wrapper around an OpenAI
  chat model. Requires ``OPENAI_API_KEY`` in the environment; LiteLLM reads it
  automatically. The ``litellm`` package must be installed.
- ``gemini`` → returns the bare model-name string, which ADK resolves natively
  via google-genai. Kept as a fallback so the pipeline can flip back without a
  code change.

Env vars
--------
LLM_PROVIDER       openai | gemini            (default: openai)
OPENAI_MODEL       OpenAI chat model name     (default: gpt-5.4)
OPENAI_MAX_TOKENS  max output tokens          (default: 8192)
ADK_GEMINI_MODEL   Gemini model name          (default: gemini-2.0-flash)
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


def _provider() -> str:
    return os.environ.get("LLM_PROVIDER", "openai").strip().lower()


def _max_tokens() -> int:
    try:
        return int(os.environ.get("OPENAI_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)).strip())
    except ValueError:
        return DEFAULT_MAX_TOKENS


def make_text_model() -> Any:
    """Return the model object/string the ADK ``LlmAgent`` should use.

    For OpenAI this is a ``LiteLlm`` instance; for Gemini it is a plain string.
    ``LlmAgent(model=...)`` accepts either form.
    """
    provider = _provider()

    if provider == "gemini":
        return os.environ.get("ADK_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

    if provider == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set. "
                "Add it to .env (or the Render env) and retry."
            )
        # Imported lazily so a Gemini-only deploy doesn't need litellm installed.
        from google.adk.models.lite_llm import LiteLlm

        model_name = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        # LiteLLM resolves the OpenAI provider from the "openai/" prefix and
        # reads OPENAI_API_KEY from the environment. Extra kwargs are forwarded
        # to litellm.completion().
        return LiteLlm(model=f"openai/{model_name}", max_tokens=_max_tokens())

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. Use 'openai' or 'gemini'."
    )


def active_model_name() -> str:
    """Bare model name for the active provider, e.g. 'gpt-4o'.

    Used by telemetry to price a call. Unlike ``model_label()`` this carries no
    decoration, so it can be looked up directly in the cost table.
    """
    if _provider() == "gemini":
        return os.environ.get("ADK_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    return os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)


def model_label() -> str:
    """Human-readable description of the active model, for logs."""
    provider = _provider()
    if provider == "gemini":
        return f"gemini:{os.environ.get('ADK_GEMINI_MODEL', DEFAULT_GEMINI_MODEL)}"
    model = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    return f"openai:{model} (max_tokens={_max_tokens()})"
