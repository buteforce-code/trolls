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
OPENAI_MODEL       OpenAI chat model name     (default: gpt-4o)
ADK_GEMINI_MODEL   Gemini model name          (default: gemini-2.0-flash)
"""
from __future__ import annotations

import os
from typing import Any

DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


def _provider() -> str:
    return os.environ.get("LLM_PROVIDER", "openai").strip().lower()


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
        # reads OPENAI_API_KEY from the environment.
        return LiteLlm(model=f"openai/{model_name}")

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. Use 'openai' or 'gemini'."
    )


def model_label() -> str:
    """Human-readable description of the active model, for logs."""
    provider = _provider()
    if provider == "gemini":
        return f"gemini:{os.environ.get('ADK_GEMINI_MODEL', DEFAULT_GEMINI_MODEL)}"
    return f"openai:{os.environ.get('OPENAI_MODEL', DEFAULT_OPENAI_MODEL)}"
