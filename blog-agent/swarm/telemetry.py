"""Agent telemetry — per-agent events, token accounting and a spend ceiling.

Why this exists
---------------
Before this module the only visibility into a pipeline run was raw stdout written
to a file in ``os.tmpdir()``, keyed by slug, overwritten on every re-run and lost
on every Render restart. That made three separate things impossible:

1. **Debugging.** "Which agent was slow / which tool call failed" was unanswerable.
2. **Pricing.** ``content_engine_features.md`` §14 flags that every cost figure in
   the catalogue is estimated from the infra table, never measured.
3. **Selling.** Watching eight agents research, argue, and get rejected by a
   quality gate is the most persuasive artefact this product has, and it was
   invisible.

So each agent invocation and each gate verdict is now an event with a duration,
a token count and an estimated cost, persisted to ``agent_runs`` / ``agent_events``.

Like ``swarm/geo.py`` this module is deliberately **import-clean** — no supabase,
no ADK, no dotenv — so it is directly testable. The database is reached through an
injected sink, not an import.

    python tests/test_telemetry.py
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

# ── Event kinds ──────────────────────────────────────────────────────────────
# Deliberately small and closed. A viewer renders each kind differently, so a
# free-text kind would silently fall through to the default branch.
KIND_AGENT_STARTED = "agent_started"
KIND_AGENT_FINISHED = "agent_finished"
KIND_AGENT_FAILED = "agent_failed"
KIND_AGENT_RETRY = "agent_retry"
KIND_GATE_PASSED = "gate_passed"
KIND_GATE_FAILED = "gate_failed"
KIND_STAGE = "stage"
KIND_NOTE = "note"

EVENT_KINDS: frozenset[str] = frozenset({
    KIND_AGENT_STARTED,
    KIND_AGENT_FINISHED,
    KIND_AGENT_FAILED,
    KIND_AGENT_RETRY,
    KIND_GATE_PASSED,
    KIND_GATE_FAILED,
    KIND_STAGE,
    KIND_NOTE,
})

RUN_STATUS_RUNNING = "running"
RUN_STATUS_SUCCEEDED = "succeeded"
RUN_STATUS_FAILED = "failed"


# ── Cost model ───────────────────────────────────────────────────────────────
# USD per 1,000,000 tokens, (input, output).
#
# ⚠️ These are list prices captured 2026-08-02 from developers.openai.com/api/docs/pricing,
# not a live feed. They exist to make relative cost visible and to enforce a
# ceiling — not for invoicing. Vendor pricing drifts; re-check before any figure
# derived from this reaches a client quote. Override a single model without a
# deploy via LLM_PRICE_OVERRIDES, e.g.
#   LLM_PRICE_OVERRIDES='{"openai/gpt-4o": [2.5, 10.0]}'
#
# gpt-5.4 is the active writer model. Its output token is 1.5x gpt-4o's, which is
# the deliberate trade: gpt-4o was cheaper per call and could not clear the length
# floor, so it burned a failed run plus an expansion pass instead of one call.
DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "gpt-5.4":              (2.50, 15.00),
    "gpt-5.4-mini":         (0.75,  4.50),
    "gpt-4.1":              (2.00,  8.00),
    "gpt-4o":               (2.50, 10.00),
    "gpt-4o-mini":          (0.15,  0.60),
    "gemini-2.0-flash":     (0.10,  0.40),
    "gemini-2.5-flash":     (0.30,  2.50),
}

# Flat per-image cost, USD. Images are off by default (ENABLE_IMAGES=false) but
# they are the most expensive module in the catalogue, so they are metered.
IMAGE_PRICES: dict[str, float] = {
    "dall-e-3":     0.040,
    "gpt-image-1":  0.040,
}

UNKNOWN_MODEL_PRICE: tuple[float, float] = (0.0, 0.0)

DEFAULT_MAX_RUN_COST_USD = 3.00
DEFAULT_MAX_DAILY_COST_USD = 25.00

# Backstop for models absent from the price table.
#
# An unpriced model costs $0 by this module's arithmetic, which would make the
# USD ceilings a silent no-op — exactly the wrong failure mode, and easy to reach
# by a model-name typo or a provider bumping a version. Tokens are always
# counted regardless of price, so this ceiling still bites. Sized at roughly ten
# times a normal full run (~40k tokens) so it never fires on healthy traffic.
DEFAULT_MAX_RUN_TOKENS = 400_000

# Models we have already warned about, so an unpriced model logs once per
# process rather than once per agent call.
_WARNED_MODELS: set[str] = set()


class SpendCeilingExceeded(RuntimeError):
    """Raised when a run would push spend past its configured ceiling.

    Deliberately a hard stop rather than a warning. The unauthenticated
    ``/api/run`` endpoint made unbounded spend a one-request attack, and
    ``content_engine_features.md`` §7.3 already flags re-runs as the margin leak
    with "no natural ceiling". This is the ceiling.
    """


def _normalise_model(model: str) -> str:
    """Strip a LiteLLM provider prefix so 'openai/gpt-4o' prices as 'gpt-4o'."""
    name = (model or "").strip()
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    return name


def _price_overrides() -> dict[str, tuple[float, float]]:
    raw = os.environ.get("LLM_PRICE_OVERRIDES", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    out: dict[str, tuple[float, float]] = {}
    for key, value in (parsed or {}).items():
        if isinstance(value, (list, tuple)) and len(value) == 2:
            try:
                out[_normalise_model(str(key))] = (float(value[0]), float(value[1]))
            except (TypeError, ValueError):
                continue
    return out


def price_for(model: str) -> tuple[float, float]:
    """(input, output) USD per 1M tokens. (0, 0) for an unpriced model."""
    name = _normalise_model(model)
    return _price_overrides().get(name) or DEFAULT_PRICES.get(name, UNKNOWN_MODEL_PRICE)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimated USD for one call. Unknown models cost 0 — visible, not fatal.

    "Not fatal" is the deliberate choice, but it has a consequence: a $0 estimate
    makes the USD ceilings inert for that model. So an unpriced model warns once,
    and `RunRecorder.check_ceiling` falls back to the token ceiling.
    """
    in_rate, out_rate = price_for(model)
    if model and in_rate == 0 and out_rate == 0 and model not in _WARNED_MODELS:
        _WARNED_MODELS.add(model)
        print(
            f"[swarm] No price known for model '{model}' — cost will read $0 and the "
            f"USD ceilings cannot bind it. The token ceiling (MAX_RUN_TOKENS) still "
            f"applies. Add it to DEFAULT_PRICES or set LLM_PRICE_OVERRIDES.",
            flush=True,
        )
    total = (max(0, input_tokens) * in_rate + max(0, output_tokens) * out_rate) / 1_000_000
    return round(total, 6)


def estimate_image_cost(model: str, count: int = 1) -> float:
    return round(IMAGE_PRICES.get(_normalise_model(model), 0.0) * max(0, count), 6)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def max_run_cost_usd() -> float:
    return _env_float("MAX_RUN_COST_USD", DEFAULT_MAX_RUN_COST_USD)


def max_daily_cost_usd() -> float:
    return _env_float("MAX_DAILY_COST_USD", DEFAULT_MAX_DAILY_COST_USD)


def max_run_tokens() -> int:
    try:
        return int(_env_float("MAX_RUN_TOKENS", DEFAULT_MAX_RUN_TOKENS))
    except (TypeError, ValueError):
        return DEFAULT_MAX_RUN_TOKENS


# ── Token extraction ─────────────────────────────────────────────────────────
# ADK surfaces usage differently depending on provider (google-genai native vs
# the LiteLlm wrapper), and some events carry no usage at all. Rather than guess
# a shape, probe the known attribute names and fall back to zero.
_INPUT_KEYS = ("prompt_token_count", "input_tokens", "prompt_tokens")
_OUTPUT_KEYS = ("candidates_token_count", "output_tokens", "completion_tokens")


def _first_int(source: Any, keys: Iterable[str]) -> int:
    for key in keys:
        value = None
        if isinstance(source, dict):
            value = source.get(key)
        else:
            value = getattr(source, key, None)
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
    return 0


def extract_usage(event: Any) -> tuple[int, int]:
    """(input_tokens, output_tokens) from one ADK event. (0, 0) when absent."""
    usage = getattr(event, "usage_metadata", None)
    if usage is None and isinstance(event, dict):
        usage = event.get("usage_metadata") or event.get("usage")
    if usage is None:
        return 0, 0
    return _first_int(usage, _INPUT_KEYS), _first_int(usage, _OUTPUT_KEYS)


# ── Events ───────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class AgentEvent:
    """One thing that happened, in order, during a run."""
    seq: int
    agent: str
    kind: str
    detail: dict[str, Any] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    at: str = ""

    def to_row(self, run_id: str) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "seq": self.seq,
            "agent": self.agent,
            "kind": self.kind,
            "detail": self.detail,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "duration_ms": self.duration_ms,
            "at": self.at,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# A sink receives (table_name, row_dict). Injected so this module never imports
# supabase and stays unit-testable.
Sink = Callable[[str, dict[str, Any]], None]


def null_sink(_table: str, _row: dict[str, Any]) -> None:
    """Discard everything. Used by tests and by CLI runs with no DB configured."""


class RunRecorder:
    """Records one pipeline run: its events, its token spend, its ceiling.

    Never raises from a sink failure — telemetry must not be able to kill a
    content run. The one exception it *does* raise is SpendCeilingExceeded,
    which is a deliberate stop, not a telemetry error.
    """

    def __init__(
        self,
        topic_slug: str,
        topic_id: str | None = None,
        trigger: str = "manual",
        sink: Sink | None = None,
        run_id: str | None = None,
        prior_day_cost_usd: float = 0.0,
        echo: bool = True,
    ) -> None:
        self.run_id = run_id or str(uuid.uuid4())
        self.topic_slug = topic_slug
        self.topic_id = topic_id
        self.trigger = trigger
        self._sink: Sink = sink or null_sink
        self._echo = echo
        self._seq = 0
        self._started = time.monotonic()
        self.events: list[AgentEvent] = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self.prior_day_cost_usd = max(0.0, prior_day_cost_usd)
        self.status = RUN_STATUS_RUNNING
        self._open_run()

    # ── lifecycle ────────────────────────────────────────────────────────────
    def _open_run(self) -> None:
        self._write("agent_runs", {
            "id": self.run_id,
            "topic_slug": self.topic_slug,
            "topic_id": self.topic_id,
            "trigger": self.trigger,
            "status": RUN_STATUS_RUNNING,
            "started_at": _now_iso(),
        })

    def finish(self, status: str = RUN_STATUS_SUCCEEDED, error: str | None = None) -> None:
        self.status = status
        self._write("agent_runs", {
            "id": self.run_id,
            "status": status,
            "finished_at": _now_iso(),
            "duration_ms": self.elapsed_ms,
            "total_input_tokens": self.input_tokens,
            "total_output_tokens": self.output_tokens,
            "total_cost_usd": round(self.cost_usd, 6),
            "agent_count": self.agent_count,
            "error": (error or "")[:2000] or None,
        })

    @property
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._started) * 1000)

    @property
    def agent_count(self) -> int:
        return sum(1 for e in self.events if e.kind == KIND_AGENT_FINISHED)

    # ── emitting ─────────────────────────────────────────────────────────────
    def emit(
        self,
        agent: str,
        kind: str,
        detail: dict[str, Any] | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        duration_ms: int = 0,
    ) -> AgentEvent:
        if kind not in EVENT_KINDS:
            kind = KIND_NOTE
        self._seq += 1
        event = AgentEvent(
            seq=self._seq,
            agent=agent,
            kind=kind,
            detail=detail or {},
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost_usd, 6),
            duration_ms=duration_ms,
            at=_now_iso(),
        )
        self.events.append(event)
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += event.cost_usd
        self._write("agent_events", event.to_row(self.run_id))
        if self._echo:
            self._print(event)
        return event

    def gate(self, name: str, passed: bool, reason: str = "", attempt: int = 1) -> AgentEvent:
        """Record a deterministic gate verdict (GEO, length, link validator).

        These are not agents, but they are the highest-signal moments in a run —
        a gate rejecting a draft is exactly what a prospect should see happen.
        """
        return self.emit(
            agent=name,
            kind=KIND_GATE_PASSED if passed else KIND_GATE_FAILED,
            detail={"reason": reason[:1500], "attempt": attempt} if reason else {"attempt": attempt},
        )

    def stage(self, name: str, detail: dict[str, Any] | None = None) -> AgentEvent:
        return self.emit(agent=name, kind=KIND_STAGE, detail=detail)

    # ── spend ceiling ────────────────────────────────────────────────────────
    def check_ceiling(self) -> None:
        """Raise before starting more work if this run has spent enough.

        Checked *before* each agent rather than after, so the ceiling bounds what
        can still be spent rather than reporting what already was.
        """
        run_ceiling = max_run_cost_usd()
        if run_ceiling > 0 and self.cost_usd >= run_ceiling:
            raise SpendCeilingExceeded(
                f"Run {self.run_id[:8]} reached ${self.cost_usd:.4f} of its "
                f"${run_ceiling:.2f} per-run ceiling (MAX_RUN_COST_USD). "
                f"Raise the ceiling or split the work."
            )
        day_ceiling = max_daily_cost_usd()
        day_total = self.prior_day_cost_usd + self.cost_usd
        if day_ceiling > 0 and day_total >= day_ceiling:
            raise SpendCeilingExceeded(
                f"Daily spend reached ${day_total:.4f} of the ${day_ceiling:.2f} "
                f"ceiling (MAX_DAILY_COST_USD). Pipeline paused until tomorrow "
                f"or until the ceiling is raised."
            )
        # Backstop: tokens are counted even when the model has no price, so this
        # is the only ceiling that binds an unpriced model.
        token_ceiling = max_run_tokens()
        tokens = self.input_tokens + self.output_tokens
        if token_ceiling > 0 and tokens >= token_ceiling:
            raise SpendCeilingExceeded(
                f"Run {self.run_id[:8]} used {tokens:,} tokens, at or past the "
                f"{token_ceiling:,} MAX_RUN_TOKENS backstop. This ceiling exists "
                f"so an unpriced model cannot spend without limit."
            )

    # ── output ───────────────────────────────────────────────────────────────
    def _print(self, event: AgentEvent) -> None:
        bits = [f"[swarm] {event.agent} · {event.kind}"]
        if event.duration_ms:
            bits.append(f"{event.duration_ms / 1000:.1f}s")
        if event.input_tokens or event.output_tokens:
            bits.append(f"{event.input_tokens}in/{event.output_tokens}out")
        if event.cost_usd:
            bits.append(f"${event.cost_usd:.4f}")
        reason = event.detail.get("reason") if event.detail else None
        if reason:
            bits.append(str(reason)[:160])
        print(" · ".join(bits), flush=True)

    def _write(self, table: str, row: dict[str, Any]) -> None:
        try:
            self._sink(table, row)
        except Exception as exc:  # telemetry must never kill a content run
            print(f"[swarm] telemetry sink failed ({table}): {exc}", flush=True)

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "topic_slug": self.topic_slug,
            "status": self.status,
            "agents": self.agent_count,
            "events": len(self.events),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "duration_ms": self.elapsed_ms,
        }


# ── No-op recorder ───────────────────────────────────────────────────────────
class NullRecorder(RunRecorder):
    """Recorder that records nothing and never blocks on spend.

    Lets call sites use ``recorder.emit(...)`` unconditionally instead of
    guarding every call with ``if recorder is not None``.
    """

    def __init__(self) -> None:
        super().__init__(topic_slug="", sink=null_sink, echo=False)

    def emit(self, *args: Any, **kwargs: Any) -> AgentEvent:  # type: ignore[override]
        return AgentEvent(seq=0, agent="", kind=KIND_NOTE)

    def check_ceiling(self) -> None:
        return

    def finish(self, status: str = RUN_STATUS_SUCCEEDED, error: str | None = None) -> None:
        self.status = status
