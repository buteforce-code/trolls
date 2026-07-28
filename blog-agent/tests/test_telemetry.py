"""Telemetry + spend-ceiling tests.

The ceiling is a security control, not a nicety — `/api/run` was unauthenticated,
which made unbounded LLM spend a one-request attack. So the adversarial tests
here are the ones that matter: a sink that throws must not kill a run, and the
ceiling must trip *before* the next agent starts rather than after it finishes.

`swarm/telemetry.py` is import-clean (no supabase, no ADK, no dotenv), so this
imports it directly.

    python tests/test_telemetry.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm import telemetry as tm  # noqa: E402


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


class CollectingSink:
    """Sink that records every (table, row) it is handed."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, dict]] = []

    def __call__(self, table: str, row: dict) -> None:
        self.rows.append((table, row))

    def of(self, table: str) -> list[dict]:
        return [r for t, r in self.rows if t == table]


def _recorder(sink=None, prior: float = 0.0) -> tm.RunRecorder:
    return tm.RunRecorder(
        topic_slug="test-post",
        topic_id="00000000-0000-0000-0000-000000000001",
        trigger="test",
        sink=sink or tm.null_sink,
        prior_day_cost_usd=prior,
        echo=False,
    )


# ── cost model ───────────────────────────────────────────────────────────────
def test_cost_estimation() -> int:
    f = 0
    # 1M in + 1M out on gpt-4o = 2.50 + 10.00
    cost = tm.estimate_cost("gpt-4o", 1_000_000, 1_000_000)
    if abs(cost - 12.50) > 1e-6:
        _fail(f"gpt-4o 1M/1M should cost 12.50, got {cost}")
        f += 1
    # LiteLLM provider prefix must not defeat the price lookup.
    if tm.estimate_cost("openai/gpt-4o", 1_000_000, 0) != tm.estimate_cost("gpt-4o", 1_000_000, 0):
        _fail("provider prefix 'openai/' changed the price")
        f += 1
    # An unpriced model costs 0 rather than raising.
    if tm.estimate_cost("some-new-model", 1_000_000, 1_000_000) != 0.0:
        _fail("unknown model should cost 0, not raise")
        f += 1
    # Negative token counts must not produce a credit.
    if tm.estimate_cost("gpt-4o", -5_000_000, -5_000_000) != 0.0:
        _fail("negative tokens should clamp to 0")
        f += 1
    return f


def test_price_override_from_env() -> int:
    f = 0
    os.environ["LLM_PRICE_OVERRIDES"] = '{"openai/gpt-4o": [1.0, 2.0]}'
    try:
        if tm.price_for("gpt-4o") != (1.0, 2.0):
            _fail(f"env override ignored, got {tm.price_for('gpt-4o')}")
            f += 1
        os.environ["LLM_PRICE_OVERRIDES"] = "{not json"
        if tm.price_for("gpt-4o") != tm.DEFAULT_PRICES["gpt-4o"]:
            _fail("malformed override should fall back to defaults, not crash")
            f += 1
    finally:
        os.environ.pop("LLM_PRICE_OVERRIDES", None)
    return f


def test_image_cost_is_metered() -> int:
    f = 0
    if tm.estimate_image_cost("dall-e-3", 3) != round(0.040 * 3, 6):
        _fail("image cost should scale with count")
        f += 1
    if tm.estimate_image_cost("unknown-imager", 5) != 0.0:
        _fail("unknown image model should cost 0")
        f += 1
    return f


# ── usage extraction ─────────────────────────────────────────────────────────
class _Usage:
    def __init__(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


class _Event:
    def __init__(self, usage) -> None:
        self.usage_metadata = usage


def test_usage_extraction_across_provider_shapes() -> int:
    f = 0
    gemini = _Event(_Usage(prompt_token_count=100, candidates_token_count=50))
    if tm.extract_usage(gemini) != (100, 50):
        _fail(f"gemini-shaped usage misread: {tm.extract_usage(gemini)}")
        f += 1
    openai = _Event(_Usage(prompt_tokens=200, completion_tokens=75))
    if tm.extract_usage(openai) != (200, 75):
        _fail(f"openai-shaped usage misread: {tm.extract_usage(openai)}")
        f += 1
    litellm = _Event({"input_tokens": 10, "output_tokens": 20})
    if tm.extract_usage(litellm) != (10, 20):
        _fail(f"dict-shaped usage misread: {tm.extract_usage(litellm)}")
        f += 1
    # An event with no usage at all must be (0, 0), not an exception.
    if tm.extract_usage(_Event(None)) != (0, 0):
        _fail("missing usage should be (0, 0)")
        f += 1
    if tm.extract_usage(object()) != (0, 0):
        _fail("arbitrary object should be (0, 0)")
        f += 1
    return f


# ── recording ────────────────────────────────────────────────────────────────
def test_events_are_sequenced_and_totalled() -> int:
    f = 0
    sink = CollectingSink()
    rec = _recorder(sink)
    rec.emit("research_agent", tm.KIND_AGENT_FINISHED, input_tokens=1000, output_tokens=500,
             cost_usd=tm.estimate_cost("gpt-4o", 1000, 500))
    rec.emit("writer_agent", tm.KIND_AGENT_FINISHED, input_tokens=2000, output_tokens=3000,
             cost_usd=tm.estimate_cost("gpt-4o", 2000, 3000))

    seqs = [e.seq for e in rec.events]
    if seqs != [1, 2]:
        _fail(f"events should be sequenced 1..n, got {seqs}")
        f += 1
    if rec.input_tokens != 3000 or rec.output_tokens != 3500:
        _fail(f"token totals wrong: {rec.input_tokens}/{rec.output_tokens}")
        f += 1
    if rec.agent_count != 2:
        _fail(f"agent_count should count finished agents, got {rec.agent_count}")
        f += 1
    if len(sink.of("agent_events")) != 2:
        _fail("every event should reach the sink")
        f += 1
    if not sink.of("agent_runs"):
        _fail("opening a recorder should write an agent_runs row")
        f += 1
    return f


def test_gate_verdicts_are_recorded_with_reason() -> int:
    f = 0
    rec = _recorder()
    rec.gate("geo_gate", passed=False, reason="Only 1 question-form H2 (2 needed)", attempt=1)
    rec.gate("geo_gate", passed=True, attempt=2)
    kinds = [e.kind for e in rec.events]
    if kinds != [tm.KIND_GATE_FAILED, tm.KIND_GATE_PASSED]:
        _fail(f"gate verdicts misrecorded: {kinds}")
        f += 1
    if "question-form H2" not in rec.events[0].detail.get("reason", ""):
        _fail("gate failure must carry the repair reason — it is the demo moment")
        f += 1
    if rec.events[1].detail.get("attempt") != 2:
        _fail("retry attempt number not recorded")
        f += 1
    # A gate is not an agent; it must not inflate agent_count.
    if rec.agent_count != 0:
        _fail(f"gates should not count as agents, got {rec.agent_count}")
        f += 1
    return f


def test_unknown_event_kind_is_coerced_not_dropped() -> int:
    f = 0
    rec = _recorder()
    ev = rec.emit("x", "totally_made_up")
    if ev.kind != tm.KIND_NOTE:
        _fail(f"unknown kind should coerce to note, got {ev.kind}")
        f += 1
    if len(rec.events) != 1:
        _fail("unknown kind should still be recorded")
        f += 1
    return f


def test_sink_failure_never_kills_the_run() -> int:
    f = 0

    def exploding_sink(_table: str, _row: dict) -> None:
        raise RuntimeError("supabase is down")

    try:
        rec = _recorder(exploding_sink)
        rec.emit("writer_agent", tm.KIND_AGENT_FINISHED, input_tokens=10, output_tokens=10)
        rec.finish()
    except Exception as exc:
        _fail(f"a failing sink must not propagate, but raised: {exc}")
        return f + 1
    if rec.input_tokens != 10:
        _fail("totals should still accumulate when the sink is broken")
        f += 1
    return f


# ── spend ceiling ────────────────────────────────────────────────────────────
def test_run_ceiling_trips_before_the_next_agent() -> int:
    f = 0
    os.environ["MAX_RUN_COST_USD"] = "0.50"
    os.environ["MAX_DAILY_COST_USD"] = "1000"
    try:
        rec = _recorder()
        rec.check_ceiling()  # nothing spent yet — must not raise
        rec.emit("writer_agent", tm.KIND_AGENT_FINISHED, cost_usd=0.60)
        try:
            rec.check_ceiling()
            _fail("ceiling did not trip after exceeding MAX_RUN_COST_USD")
            f += 1
        except tm.SpendCeilingExceeded as exc:
            if "MAX_RUN_COST_USD" not in str(exc):
                _fail("ceiling error should name the env var to raise")
                f += 1
    finally:
        os.environ.pop("MAX_RUN_COST_USD", None)
        os.environ.pop("MAX_DAILY_COST_USD", None)
    return f


def test_daily_ceiling_counts_prior_spend() -> int:
    f = 0
    os.environ["MAX_RUN_COST_USD"] = "1000"
    os.environ["MAX_DAILY_COST_USD"] = "10"
    try:
        # This run has spent nothing, but the day is already at 9.95.
        rec = _recorder(prior=9.95)
        rec.emit("research_agent", tm.KIND_AGENT_FINISHED, cost_usd=0.10)
        try:
            rec.check_ceiling()
            _fail("daily ceiling ignored prior_day_cost_usd")
            f += 1
        except tm.SpendCeilingExceeded:
            pass
    finally:
        os.environ.pop("MAX_RUN_COST_USD", None)
        os.environ.pop("MAX_DAILY_COST_USD", None)
    return f


def test_token_backstop_binds_an_unpriced_model() -> int:
    """An unpriced model costs $0, which would make the USD ceilings inert.

    This is the scenario a model-name typo or a provider version bump lands you
    in, so the token ceiling has to catch it.
    """
    f = 0
    os.environ["MAX_RUN_COST_USD"] = "1000"
    os.environ["MAX_DAILY_COST_USD"] = "1000"
    os.environ["MAX_RUN_TOKENS"] = "5000"
    try:
        rec = _recorder()
        # A model nobody priced: cost stays 0 no matter how many tokens burn.
        cost = tm.estimate_cost("gpt-9-turbo-preview", 4_000, 4_000)
        if cost != 0.0:
            _fail("precondition wrong: the model should be unpriced")
            f += 1
        rec.emit("writer_agent", tm.KIND_AGENT_FINISHED,
                 input_tokens=4_000, output_tokens=4_000, cost_usd=cost)
        try:
            rec.check_ceiling()
            _fail("token backstop did not trip for an unpriced model")
            f += 1
        except tm.SpendCeilingExceeded as exc:
            if "MAX_RUN_TOKENS" not in str(exc):
                _fail("backstop error should name MAX_RUN_TOKENS")
                f += 1
    finally:
        for key in ("MAX_RUN_COST_USD", "MAX_DAILY_COST_USD", "MAX_RUN_TOKENS"):
            os.environ.pop(key, None)
    return f


def test_token_backstop_does_not_fire_on_a_normal_run() -> int:
    f = 0
    os.environ["MAX_RUN_TOKENS"] = str(tm.DEFAULT_MAX_RUN_TOKENS)
    try:
        rec = _recorder()
        # Roughly a full eight-agent post.
        rec.emit("writer_agent", tm.KIND_AGENT_FINISHED, input_tokens=30_000, output_tokens=12_000)
        rec.check_ceiling()
    except tm.SpendCeilingExceeded:
        _fail("backstop fired on a normal-sized run — the default is too tight")
        f += 1
    finally:
        os.environ.pop("MAX_RUN_TOKENS", None)
    return f


def test_ceiling_of_zero_disables_it() -> int:
    f = 0
    os.environ["MAX_RUN_COST_USD"] = "0"
    os.environ["MAX_DAILY_COST_USD"] = "0"
    try:
        rec = _recorder(prior=9999)
        rec.emit("writer_agent", tm.KIND_AGENT_FINISHED, cost_usd=500)
        rec.check_ceiling()  # must not raise
    except tm.SpendCeilingExceeded:
        _fail("a ceiling of 0 should mean 'unlimited', not 'always trip'")
        f += 1
    finally:
        os.environ.pop("MAX_RUN_COST_USD", None)
        os.environ.pop("MAX_DAILY_COST_USD", None)
    return f


def test_malformed_ceiling_env_falls_back_to_default() -> int:
    f = 0
    os.environ["MAX_RUN_COST_USD"] = "not-a-number"
    try:
        if tm.max_run_cost_usd() != tm.DEFAULT_MAX_RUN_COST_USD:
            _fail("malformed MAX_RUN_COST_USD should fall back to the default")
            f += 1
    finally:
        os.environ.pop("MAX_RUN_COST_USD", None)
    return f


def test_null_recorder_is_inert() -> int:
    f = 0
    rec = tm.NullRecorder()
    rec.emit("writer_agent", tm.KIND_AGENT_FINISHED, cost_usd=9999)
    rec.check_ceiling()  # must never raise regardless of spend
    rec.finish()
    if rec.events:
        _fail("NullRecorder should not accumulate events")
        f += 1
    return f


def test_finish_writes_totals() -> int:
    f = 0
    sink = CollectingSink()
    rec = _recorder(sink)
    rec.emit("writer_agent", tm.KIND_AGENT_FINISHED, input_tokens=100, output_tokens=200, cost_usd=0.01)
    rec.finish(tm.RUN_STATUS_SUCCEEDED)
    final = sink.of("agent_runs")[-1]
    if final.get("status") != tm.RUN_STATUS_SUCCEEDED:
        _fail(f"final status not written: {final.get('status')}")
        f += 1
    if final.get("total_output_tokens") != 200:
        _fail(f"totals not written on finish: {final}")
        f += 1
    if final.get("id") != rec.run_id:
        _fail("final row must carry the same run id so the upsert lands")
        f += 1
    return f


def main() -> int:
    tests = [
        ("cost estimation", test_cost_estimation),
        ("price override from env", test_price_override_from_env),
        ("image cost metered", test_image_cost_is_metered),
        ("usage extraction across providers", test_usage_extraction_across_provider_shapes),
        ("events sequenced and totalled", test_events_are_sequenced_and_totalled),
        ("gate verdicts recorded", test_gate_verdicts_are_recorded_with_reason),
        ("unknown kind coerced", test_unknown_event_kind_is_coerced_not_dropped),
        ("sink failure never kills run", test_sink_failure_never_kills_the_run),
        ("run ceiling trips early", test_run_ceiling_trips_before_the_next_agent),
        ("daily ceiling counts prior spend", test_daily_ceiling_counts_prior_spend),
        ("token backstop binds unpriced model", test_token_backstop_binds_an_unpriced_model),
        ("token backstop quiet on normal run", test_token_backstop_does_not_fire_on_a_normal_run),
        ("zero ceiling disables", test_ceiling_of_zero_disables_it),
        ("malformed ceiling env", test_malformed_ceiling_env_falls_back_to_default),
        ("null recorder inert", test_null_recorder_is_inert),
        ("finish writes totals", test_finish_writes_totals),
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
