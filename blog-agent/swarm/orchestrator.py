"""
Buteforce Blog Agent — Swarm Orchestrator
Stateful pipeline: research → verify → write → humanise → verify → publish
State lives in Supabase. Each stage is a separate ADK agent run.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Force UTF-8 output on Windows to avoid CP1252 encoding errors
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv

# Load env from repo root
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from supabase import create_client, Client
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from swarm.agents.research import make_research_agent
from swarm.agents.auditor import make_audit_agent
from swarm.agents.writer import make_writer_agent
from swarm.agents.humaniser import make_humaniser_agent
from swarm.agents.publisher import make_publisher_agent
from swarm.agents.imager import run_imaging
from swarm.agents.linker import run_linking
from swarm.agents.schema_ld import run_schema_ld
from swarm.agents.social import run_social
from swarm import geo
from swarm import guards
from swarm import telemetry as tm
from swarm.telemetry_db import make_recorder

if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ── Supabase ────────────────────────────────────────────────────────────────
def _db() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# ── Status transitions ───────────────────────────────────────────────────────
PIPELINE = [
    "queued",
    "researching",
    "verifying_research",
    "writing",
    "verifying_draft",
    "publishing",
    "published",
]

STATUS_LABELS = {
    "queued":             "Queued",
    "researching":        "Researching...",
    "verifying_research": "Research Ready — Awaiting Approval",
    "writing":            "Writing...",
    "verifying_draft":    "Draft Ready — Awaiting Approval",
    "scheduled":          "Scheduled — Auto-publishes at its slot",
    "publishing":         "Publishing...",
    "published":          "Published ✓",
    "cancelled":          "Cancelled",
    "failed":             "Failed",
}


def _update_status(slug: str, status: str) -> None:
    _db().table("topics").update({
        "status": status,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }).eq("slug", slug).execute()


def _upsert_post(topic_id: str, data: dict) -> None:
    data["topic_id"] = topic_id
    data["updated_at"] = datetime.utcnow().isoformat() + "Z"
    _db().table("blog_posts").upsert(data, on_conflict="topic_id").execute()


def _mark_failed(slug: str, topic_id: str, where: str, err: Exception | str) -> None:
    """Set status=failed and persist a short error so the dashboard can surface it.
    Safe to call even if the blog_posts row is missing — upsert will create it.
    """
    msg = str(err) if err else "unknown"
    detail = f"[{where}] {msg}"[:4000]
    try:
        _upsert_post(topic_id, {"last_error": detail})
    except Exception as inner:
        print(f"[orchestrator] failed to persist last_error: {inner}", flush=True)
    _update_status(slug, "failed")


def _record_step_failure(topic_id: str, step: str, err: Exception | str) -> None:
    """Surface a non-blocking stage failure on the dashboard, not just in the log.

    Schema and social are enrichment steps, so they must not kill an otherwise
    good draft. But a `print` in a background worker is invisible — schema has
    been failing silently, which is why no published post carries FAQPage
    structured data. Persisting to `last_error` makes it visible at the review
    gate while still letting the draft through.
    """
    detail = f"[{step}] {err}"[:4000]
    print(f"[writer] {step} FAILED (non-blocking, review before publish): {err}", flush=True)
    try:
        _upsert_post(topic_id, {"last_error": detail})
    except Exception as inner:
        print(f"[orchestrator] failed to persist {step} error: {inner}", flush=True)


def _get_post(topic_id: str) -> dict:
    r = _db().table("blog_posts").select("*").eq("topic_id", topic_id).limit(1).execute()
    return r.data[0] if r.data else {}


# ── Telemetry ────────────────────────────────────────────────────────────────
# One recorder per process. Module-level rather than threaded through every
# signature because the sub-runners (linker, schema, social, ideator) receive
# `_run` as a callable and cannot pass extra context through it.
_RECORDER: tm.RunRecorder = tm.NullRecorder()


def set_recorder(recorder: tm.RunRecorder) -> None:
    global _RECORDER
    _RECORDER = recorder


def get_recorder() -> tm.RunRecorder:
    return _RECORDER


def start_run(topic_slug: str, topic_id: str | None = None, trigger: str = "manual") -> tm.RunRecorder:
    """Open a recorded run and make it the active one for this process."""
    recorder = make_recorder(_db(), topic_slug, topic_id, trigger)
    set_recorder(recorder)
    return recorder


@contextmanager
def recorded_run(topic_slug: str, topic_id: str | None = None, trigger: str = "manual"):
    """Wrap a unit of pipeline work so it lands in `agent_runs` either way.

    The run is closed on the way out whatever happens, so a crashed pipeline
    still leaves a costed, inspectable record instead of a row stuck at
    `running` forever.
    """
    recorder = start_run(topic_slug, topic_id, trigger)
    try:
        yield recorder
    except tm.SpendCeilingExceeded as exc:
        print(f"[swarm] SPEND CEILING: {exc}", flush=True)
        recorder.finish(tm.RUN_STATUS_FAILED, error=str(exc))
        raise
    except Exception as exc:
        recorder.finish(tm.RUN_STATUS_FAILED, error=str(exc))
        raise
    else:
        recorder.finish(tm.RUN_STATUS_SUCCEEDED)
    finally:
        summary = recorder.summary()
        if summary.get("events"):
            print(
                f"[swarm] run {summary['run_id'][:8]} · {summary['agents']} agents · "
                f"{summary['input_tokens']}in/{summary['output_tokens']}out tokens · "
                f"${summary['cost_usd']:.4f} · {summary['duration_ms'] / 1000:.1f}s",
                flush=True,
            )
        set_recorder(tm.NullRecorder())


# ── ADK runner ───────────────────────────────────────────────────────────────
# Neither provider in this stack imposes its own request timeout — LiteLLM/OpenAI
# doesn't (llm.py passes only `model` and `max_tokens`), and the ADK Runner doesn't
# either. A stalled HTTP connection blocks the awaiting coroutine forever: no
# exception, so the retry logic below never engages and nothing ever calls
# _mark_failed. 2026-08-02: a topic sat in status=writing for 679+ minutes after
# the log showed `social_agent · agent_started` and then nothing — no crash, no
# further cost, no way out short of a manual "Re-run from scratch". This bounds
# every agent call so a hang becomes a retryable timeout instead of an indefinite
# stall. 240s is generous headroom above the slowest measured real call (the
# research agent's tool-using calls can run long; a plain writer/humaniser call
# finishes in 20-35s per the 2026-08-02 gpt-5.4 bake-off).
_AGENT_CALL_TIMEOUT_S = 240


async def _run_agent(
    agent: LlmAgent, prompt: str, session_id: str, retries: int = 3
) -> tuple[str, int, int]:
    """Run one agent to completion. Returns (text, input_tokens, output_tokens).

    Tokens accumulate across retries, not just the successful attempt — a call
    that streamed halfway and then hit a 503 still cost money, and the spend
    ceiling is only honest if it counts that.
    """
    last_err: Exception | None = None
    in_tokens = 0
    out_tokens = 0
    for attempt in range(retries):
        try:
            async def _attempt() -> str:
                nonlocal in_tokens, out_tokens
                svc = InMemorySessionService()
                session = await svc.create_session(
                    app_name=agent.name, user_id="dhyan", session_id=f"{session_id}-{attempt}"
                )
                runner = Runner(agent=agent, app_name=agent.name, session_service=svc)
                content = genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])
                parts: list[str] = []
                async for event in runner.run_async(
                    user_id="dhyan", session_id=session.id, new_message=content
                ):
                    ev_in, ev_out = tm.extract_usage(event)
                    in_tokens += ev_in
                    out_tokens += ev_out
                    if hasattr(event, "content") and event.content:
                        for p in event.content.parts:
                            if hasattr(p, "text") and p.text:
                                parts.append(p.text)
                return "".join(parts).strip()

            text = await asyncio.wait_for(_attempt(), timeout=_AGENT_CALL_TIMEOUT_S)
            return text, in_tokens, out_tokens
        except Exception as exc:
            last_err = exc
            msg = str(exc).lower()
            is_timeout = isinstance(exc, asyncio.TimeoutError)
            # Rate-limit / quota — OpenAI (429, "rate limit", "insufficient_quota")
            # and Gemini ("resource exhausted", "quota").
            is_quota = (
                "resource exhausted" in msg
                or "429" in msg
                or "quota" in msg
                or "rate limit" in msg
                or "ratelimit" in msg
            )
            # Transient capacity / server errors worth retrying — OpenAI (500/502/503,
            # "overloaded", "service unavailable"), Gemini (503/UNAVAILABLE), and a
            # connection that never returned within _AGENT_CALL_TIMEOUT_S.
            is_unavailable = (
                is_timeout
                or "503" in msg or "502" in msg or "500" in msg
                or "unavailable" in msg or "overloaded" in msg
                or "high demand" in msg or "timeout" in msg
                or "timed out" in msg or "apiconnection" in msg
            )
            if (is_quota or is_unavailable) and attempt < retries - 1:
                wait = 20 * (attempt + 1)
                reason = "Quota" if is_quota else ("Call timed out" if is_timeout else "Model unavailable (503)")
                print(f"  [WAIT] {reason}, retrying in {wait}s...", flush=True)
                await asyncio.sleep(wait)
            else:
                break
    # asyncio.TimeoutError stringifies to '' — without this, the failure this
    # timeout exists to surface would itself read as a blank, undiagnosable error.
    err_desc = (
        f"timed out after {_AGENT_CALL_TIMEOUT_S}s"
        if isinstance(last_err, asyncio.TimeoutError)
        else str(last_err)
    )
    raise RuntimeError(f"Agent '{agent.name}' failed after {retries} attempts: {err_desc}")


def _run(agent: LlmAgent, prompt: str, session_id: str) -> str:
    """Run one agent, recorded and spend-bounded.

    Every one of the ten LLM agents reaches the model through here — including
    the ones invoked by the sub-runners, which are handed this function as
    `_run_agent_fn`. That makes it the single place to meter cost and emit the
    per-agent events the swarm view renders.
    """
    recorder = get_recorder()
    # Checked *before* the call: the ceiling should bound what can still be
    # spent, not report what already was.
    recorder.check_ceiling()

    from swarm.llm import active_model_name
    model = active_model_name()
    recorder.emit(agent.name, tm.KIND_AGENT_STARTED, detail={"model": model})
    started = time.monotonic()

    # Reclaim the per-stage ADK runner/session and large tool payloads before the
    # next stage so peak RSS stays bounded on memory-constrained hosts (Render 512MB).
    try:
        text, in_tokens, out_tokens = asyncio.run(_run_agent(agent, prompt, session_id))
    except Exception as exc:
        recorder.emit(
            agent.name, tm.KIND_AGENT_FAILED,
            detail={"error": str(exc)[:1000], "model": model},
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        raise
    finally:
        import gc
        gc.collect()

    recorder.emit(
        agent.name, tm.KIND_AGENT_FINISHED,
        detail={"model": model, "chars": len(text)},
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        cost_usd=tm.estimate_cost(model, in_tokens, out_tokens),
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    return text


# ── Draft length gate ────────────────────────────────────────────────────────
# The writer prompt has always asked for 1,400–2,000 words, but nothing enforced
# it. After the Gemini → gpt-4o switch (2026-06-29) output silently halved and
# five ~550-word posts shipped before anyone noticed. The prompt is advisory;
# this gate is not.
MIN_BODY_WORDS = 1_100
_LENGTH_RETRIES = 1

# What the expansion pass aims for, not the floor it must clear. Two later stages
# shave words off a draft — the humaniser tightens prose, the GEO repair pass
# rewrites sections — and both have pushed a draft that landed exactly on the floor
# back under it. Aim inside the 1,400–2,000 band the writer prompt asks for.
_LENGTH_TARGET_WORDS = 1_450
# Per-H2 bounds for the expansion pass. 320 is the writer prompt's own "250–350
# words per section"; the ceiling stops one section from swallowing the post.
_SECTION_TARGET_WORDS = 320
_SECTION_MAX_WORDS = 420
# Enough calls to grow 5–7 thin sections, bounded so a writer that will not grow
# anything cannot burn the run's budget trying.
_MAX_EXPANSION_CALLS = 8
# Below this, an expansion call did not actually add anything — stop asking that
# section and move to the next one.
_MIN_SECTION_GROWTH = 25

# ── GEO template gate ────────────────────────────────────────────────────────
# Same lesson, second application. The answer-engine template (question H2 +
# self-contained answer, hard numbers, competitor table, "not a fit if…") is in
# the writer prompt, but AI Visibility SCAN 001 measured 0/18 citations while a
# prompt-only ban on puffery was already in place and being ignored. So the
# template is verified in the pipeline. See swarm/geo.py.
_GEO_RETRIES = 1


def _body_word_count(mdx: str) -> int:
    """Word count of the post body, excluding YAML frontmatter."""
    body = mdx.split("---", 2)[-1] if mdx.lstrip().startswith("---") else mdx
    return len(body.split())


_FRONTMATTER_BLOCK = re.compile(r"^(\s*---\s*\n.*?\n---\s*\n)(.*)$", re.DOTALL)


def _split_head_body(mdx: str) -> tuple[str, str]:
    """Return (frontmatter_block, body), keeping the `---` delimiters on the head.

    Unlike `geo.split_frontmatter`, which returns the frontmatter's *contents*, this
    keeps the block verbatim so `head + body` reassembles the file byte for byte.
    """
    m = _FRONTMATTER_BLOCK.match(mdx)
    return (m.group(1), m.group(2)) if m else ("", mdx)


_H2_LINE = re.compile(r"^##\s+\S")


def _split_body_sections(body: str) -> tuple[str, list[str]]:
    """Split a post body at top-level `##` headings, losslessly.

    Returns `(preamble, sections)` — the preamble holds the H1 and intro, and each
    section string starts with its own `## ` line and runs to the next one (H3s stay
    with their parent). `preamble + "".join(sections)` reproduces `body` exactly, so
    the expansion pass can swap one section and reassemble without disturbing the
    rest. `geo.parse_sections` cannot be used for this: it blanks out fenced code to
    avoid reading a `##` inside a fence as a heading, which is right for auditing and
    lossy for rewriting.
    """
    preamble: list[str] = []
    sections: list[list[str]] = []
    in_fence = False
    for line in body.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and _H2_LINE.match(line):
            sections.append([line])
            continue
        (sections[-1] if sections else preamble).append(line)
    return "".join(preamble), ["".join(s) for s in sections]


def _clean_expanded_section(raw: str, heading_line: str) -> str:
    """Reduce a writer reply to just the section, under its original heading.

    The heading is restored from the caller rather than trusted from the reply: the
    question-form H2s and the "not a fit if…" heading are GEO-template surfaces, and
    an expansion pass has no business renaming them.
    """
    text = raw.strip()
    fenced = re.match(r"^```[a-zA-Z]*\s*\n(.*?)\n```\s*$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if _H2_LINE.match(line):
            # Everything before the first H2 is commentary or invented frontmatter.
            rest = "\n".join(lines[idx + 1:]).strip()
            return f"{heading_line.rstrip()}\n\n{rest}\n\n"
    return f"{heading_line.rstrip()}\n\n{text}\n\n"


# ── Orchestrator ─────────────────────────────────────────────────────────────
class BlogOrchestrator:
    def __init__(self) -> None:
        from swarm.llm import make_text_model, model_label
        # Provider-agnostic: OpenAI (LiteLlm) by default, Gemini as a fallback.
        # ADK's LlmAgent accepts either a LiteLlm instance or a model-name string.
        self.model = make_text_model()
        print(f"[orchestrator] LLM model: {model_label()}", flush=True)
        self.research_agent  = make_research_agent(self.model)
        self.audit_agent     = make_audit_agent(self.model)
        self.writer_agent    = make_writer_agent(self.model)
        self.humaniser_agent = make_humaniser_agent(self.model)
        self.publisher_agent = make_publisher_agent(self.model)

    # ── Stage: Research ──────────────────────────────────────────────────────
    REQUIRED_DIGEST_FIELDS = (
        "summary", "what_people_say", "buteforce_angle", "key_facts", "source_signals",
    )

    def _extract_digest(self, raw: str, title: str) -> dict:
        """Robust JSON extraction from agent output.
        Handles markdown fences, leading commentary, and braces inside strings.
        """
        if not raw or not raw.strip():
            return {"topic": title, "_parse_error": "empty agent output", "raw": ""}

        # Strip ```json ... ``` or ``` ... ``` fences
        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw)
        candidate = fenced.group(1) if fenced else None

        # Fallback: balanced-brace scan starting from first '{'
        if not candidate:
            start = raw.find("{")
            if start < 0:
                return {"topic": title, "_parse_error": "no JSON object found", "raw": raw[:2000]}
            depth = 0
            end = -1
            in_str = False
            esc = False
            for i, ch in enumerate(raw[start:], start=start):
                if esc:
                    esc = False
                    continue
                if ch == "\\" and in_str:
                    esc = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            candidate = raw[start:end] if end > 0 else raw[start:]

        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            return {"topic": title, "_parse_error": f"JSON decode: {exc}", "raw": raw[:2000]}

    def run_research(self, topic_id: str, slug: str, title: str, tags: list[str],
                     feedback: str = "") -> dict:
        """Research the topic. `feedback` re-runs it against operator notes.

        The feedback parameter used to be missing entirely: rejecting at the
        research gate stored the note in `rejection_log` and then re-ran the
        research agent with the identical prompt, so "reject → re-run with
        feedback" silently did nothing at that gate — while working correctly at
        the draft gate.
        """
        print(f"\n[research] Starting multi-source research for: {title}", flush=True)
        _update_status(slug, "researching")

        # Pull the roadmap brief + target keyword if this topic was seeded from the
        # strategy. These steer the agent toward the intended angle and SEO target.
        brief = target_keyword = ""
        try:
            row = _db().table("topics").select("brief,target_keyword").eq("id", topic_id).limit(1).execute()
            if row.data:
                brief = (row.data[0].get("brief") or "").strip()
                target_keyword = (row.data[0].get("target_keyword") or "").strip()
        except Exception as exc:
            print(f"[research] Could not load brief/target_keyword: {exc}", flush=True)

        roadmap_section = ""
        if target_keyword:
            roadmap_section += f"\nPrimary SEO keyword to target: {target_keyword}"
        if brief:
            roadmap_section += f"\nIntended angle (from the content roadmap): {brief}"

        # Same containment as the writer path — this reaches an agent prompt.
        fenced_feedback = guards.fence_untrusted("OPERATOR FEEDBACK", feedback)
        prompt = (
            f"Research this topic thoroughly using all available tools:\n\n"
            f"Topic: {title}\nTags: {', '.join(tags)}"
            f"{roadmap_section}"
            f"{chr(10) + chr(10) + fenced_feedback if fenced_feedback else ''}"
        )

        parsed: dict = {}
        try:
            for attempt in range(2):
                raw = _run(self.research_agent, prompt, f"research-{topic_id}-{attempt}")
                print(f"[research] Agent output: {len(raw)} chars (attempt {attempt + 1})", flush=True)
                parsed = self._extract_digest(raw, title)
                missing = [f for f in self.REQUIRED_DIGEST_FIELDS if not parsed.get(f)]
                if not missing and "_parse_error" not in parsed:
                    break
                print(f"[research] Incomplete digest — missing {missing or 'parse error'}. "
                      f"{'Retrying' if attempt == 0 else 'Giving up'}.", flush=True)
                prompt = (
                    f"Your previous output was missing fields: {missing or 'unparseable JSON'}.\n"
                    f"Re-do the research and return ONLY the raw JSON object with ALL required fields populated.\n"
                    f"No markdown fences. No commentary.\n\n"
                    f"Topic: {title}\nTags: {', '.join(tags)}"
                    f"{roadmap_section}"
                )
        except Exception as exc:
            print(f"[research] CRASH: {exc}", flush=True)
            _mark_failed(slug, topic_id, "research", exc)
            raise

        # Persist whatever we got — UI surfaces _parse_error if present
        research_json = json.dumps(parsed)
        _upsert_post(topic_id, {"research_json": research_json})

        if parsed.get("_parse_error") or not parsed.get("summary"):
            print(f"[research] FAILED to get usable digest. Marking failed.", flush=True)
            _mark_failed(slug, topic_id, "research", parsed.get("_parse_error") or "no usable digest")
        else:
            _upsert_post(topic_id, {"last_error": None})
            # ── Audit gate: review the digest before writing (best-effort) ──────
            self.run_audit(topic_id, slug)
            _update_status(slug, "verifying_research")
            print(f"[research] Done. Status -> verifying_research", flush=True)
        return parsed

    # ── Stage: Audit ─────────────────────────────────────────────────────────
    def run_audit(self, topic_id: str, slug: str) -> dict:
        """Audit the stored research digest before writing.

        Best-effort and fail-open: stores the verdict in blog_posts.audit_json and
        returns it, but NEVER raises — a flaky audit must not block the pipeline.
        The autopilot reads the verdict to gate (a 'reject' triggers one re-research);
        the dashboard surfaces it at the research-review gate.
        """
        verdict: dict
        try:
            post = _get_post(topic_id)
            research_json = post.get("research_json") or "{}"
            print(f"[audit] Auditing research for {slug}...", flush=True)
            raw = _run(self.audit_agent, f"Audit this research digest:\n\n{research_json}",
                       f"audit-{topic_id}")
            verdict = self._extract_digest(raw, slug)
            if verdict.get("_parse_error"):
                # Unparseable audit = fail open so we don't stall on the gate.
                verdict = {"passed": True, "recommendation": "proceed",
                           "summary": "audit output unparseable — proceeding"}
        except Exception as exc:
            print(f"[audit] Audit failed (non-fatal): {exc}", flush=True)
            verdict = {"passed": True, "recommendation": "proceed",
                       "summary": f"audit skipped: {exc}", "_audit_error": str(exc)}

        try:
            _upsert_post(topic_id, {"audit_json": json.dumps(verdict)})
        except Exception as exc:
            print(f"[audit] could not persist audit_json: {exc}", flush=True)
        print(f"[audit] verdict: {verdict.get('recommendation', 'proceed')} "
              f"(score={verdict.get('score')})", flush=True)
        return verdict

    # ── Stage: Write → Humanise → Image → Link ──────────────────────────────
    def run_writing(self, topic_id: str, slug: str, title: str, feedback: str = "") -> dict:
        try:
            return self._run_writing_inner(topic_id, slug, title, feedback)
        except Exception as exc:
            print(f"[writer] CRASH: {exc}", flush=True)
            _mark_failed(slug, topic_id, "writer", exc)
            raise

    def _rewrite_section(
        self, section: str, target_words: int, writer_prompt: str, topic_id: str, call_no: int
    ) -> str:
        """Ask the writer to re-draft one H2 section at `target_words`, and return just it."""
        heading_line = section.splitlines()[0]
        current = len(section.split())
        raw = _run(
            self.writer_agent,
            f"{writer_prompt}\n\n"
            f"You have already drafted this post. Expand ONE section of it.\n\n"
            f"Rewrite the section below so it runs about {target_words} words — it is "
            f"currently {current}. Rules for this reply:\n"
            f"- Return that section ONLY. No frontmatter, no other sections, no commentary,\n"
            f"  no markdown fence around the whole reply.\n"
            f"- Open with its heading line exactly as given: {heading_line.strip()}\n"
            f"- Keep every markdown table, list and ### sub-heading already in it, and do not\n"
            f"  add a second ## heading.\n"
            f"- Add substance, not length: the specific example, the named mechanism, the\n"
            f"  number with its source, the failure you have watched happen on a line. If you\n"
            f"  cannot add evidence, add nothing — do not restate the section in new words.\n"
            f"- Same voice, banned words and evidence rules as the rest of the post.\n\n"
            f"SECTION:\n{section}",
            f"writer-{topic_id}-expand-{call_no}",
        )
        return _clean_expanded_section(raw, heading_line)

    def _expand_sections(self, draft: str, writer_prompt: str, topic_id: str) -> str:
        """Grow a short draft one H2 at a time until it clears `_LENGTH_TARGET_WORDS`.

        Asking the model to rewrite the whole post "but longer" does not work. gpt-4o
        stops around 1,000 output tokens whatever the prompt says (max_tokens is 4096,
        so this is the model settling, not truncation), and handing it the short draft
        anchors the retry to that length — the run on 2026-08-02 went 634 → 764 words
        against an 1,100 floor and failed. A single section is a small enough ask that
        the model does comply, and the total then follows from arithmetic rather than
        from asking more insistently.

        Returns the draft unchanged when there are no `##` sections to work with; the
        caller falls back to a whole-draft rewrite in that case.
        """
        head, body = _split_head_body(draft)
        preamble, sections = _split_body_sections(body)
        if not sections:
            print("[writer] Draft has no ## sections to expand.", flush=True)
            return draft

        def total_words() -> int:
            return len(preamble.split()) + sum(len(s.split()) for s in sections)

        exhausted: set[int] = set()
        call_no = 0
        # `call_no` counts calls actually made, so skipping an at-ceiling section
        # costs a loop turn, not one of the budgeted LLM calls.
        while call_no < _MAX_EXPANSION_CALLS:
            total = total_words()
            if total >= _LENGTH_TARGET_WORDS:
                break
            candidates = [i for i in range(len(sections)) if i not in exhausted]
            if not candidates:
                print("[writer] No section will grow further; stopping expansion.", flush=True)
                break

            # Thinnest section first: that is where the writer asserted without evidence.
            i = min(candidates, key=lambda k: len(sections[k].split()))
            current = len(sections[i].split())
            want = min(
                max(current + (_LENGTH_TARGET_WORDS - total), _SECTION_TARGET_WORDS),
                _SECTION_MAX_WORDS,
            )
            if want - current < _MIN_SECTION_GROWTH:
                # Already at the ceiling — asking would spend a call to gain nothing.
                exhausted.add(i)
                continue
            heading = sections[i].splitlines()[0].strip()
            call_no += 1
            print(
                f"[writer] Expanding section {i + 1}/{len(sections)} "
                f"({current} → ~{want} words, post at {total}): {heading[:70]}",
                flush=True,
            )

            expanded = self._rewrite_section(sections[i], want, writer_prompt, topic_id, call_no)
            grown = len(expanded.split()) - current
            # A reply several times the size asked for is the writer re-emitting the whole
            # post under one heading. Reassembling that would duplicate the article.
            if len(expanded.split()) > want * 3:
                print(
                    f"[writer] Expansion returned {len(expanded.split())} words for a "
                    f"~{want}-word section — discarding, it is not one section.",
                    flush=True,
                )
                exhausted.add(i)
                continue
            if grown < _MIN_SECTION_GROWTH:
                print(f"[writer] Section {i + 1} did not grow ({grown:+d} words).", flush=True)
                exhausted.add(i)
                continue

            sections[i] = expanded
            if len(expanded.split()) >= _SECTION_MAX_WORDS:
                exhausted.add(i)

        return head + preamble + "".join(sections)

    def _enforce_length(self, draft: str, writer_prompt: str, topic_id: str) -> str:
        """Bring the draft up to the floor, or fail the run.

        Failing loudly is deliberate — a short draft lands the topic in `failed` for
        human review instead of quietly publishing another thin post.
        """
        recorder = get_recorder()
        words = _body_word_count(draft)
        if words >= MIN_BODY_WORDS:
            recorder.gate("length_gate", passed=True, attempt=1)
            return draft

        print(
            f"[writer] Draft is {words} words, below the {MIN_BODY_WORDS} floor. "
            f"Expanding section by section...",
            flush=True,
        )
        recorder.gate(
            "length_gate", passed=False,
            reason=f"{words} words, floor is {MIN_BODY_WORDS}", attempt=1,
        )

        expanded = self._expand_sections(draft, writer_prompt, topic_id)
        if _body_word_count(expanded) > words:
            draft = expanded
        else:
            # Expansion gained nothing — either the draft has no ## sections, or the
            # writer would not grow any of them. A whole-draft rewrite is what is left.
            for attempt in range(1, _LENGTH_RETRIES + 1):
                draft = _run(
                    self.writer_agent,
                    f"{writer_prompt}\n\n"
                    f"YOUR PREVIOUS DRAFT WAS {words} WORDS — REJECTED. It must be 1,400–2,000\n"
                    f"and it must be built from 5–7 ## sections of 250–350 words each.\n"
                    f"Rewrite it in full at the required length. Do not summarise or reuse the\n"
                    f"short version. Add depth where you asserted without evidence: name the\n"
                    f"mechanism, give the specific example, cite the number and its source.\n"
                    f"Do not pad with restatement.\n\nPREVIOUS DRAFT:\n{draft}",
                    f"writer-{topic_id}-rewrite-{attempt}",
                )
                if _body_word_count(draft) >= MIN_BODY_WORDS:
                    break

        words = _body_word_count(draft)
        if words < MIN_BODY_WORDS:
            recorder.gate(
                "length_gate", passed=False,
                reason=f"{words} words after expansion, floor is {MIN_BODY_WORDS}", attempt=2,
            )
            raise RuntimeError(
                f"Writer produced {words} words after a section-by-section expansion pass "
                f"(floor is {MIN_BODY_WORDS}). Holding for human review rather than "
                f"publishing a thin post."
            )
        recorder.gate("length_gate", passed=True, attempt=2)
        print(f"[writer] Expansion brought the draft to {words} words.", flush=True)
        return draft

    def _enforce_geo_template(self, draft: str, writer_prompt: str, topic_id: str) -> str:
        """Verify the answer-engine template; re-run the writer with a repair brief if it fails.

        Metadata (`author`, `dateModified`) is injected first so the audit sees the finished
        frontmatter — those two requirements are mechanical and never bounce to the LLM.

        Same contract as `_enforce_length`: one repair attempt, then fail into `failed` for
        human review. A post without the template is invisible to answer engines, which is the
        one thing this engine exists to fix — publishing it anyway would be the silent
        degradation all over again.
        """
        recorder = get_recorder()
        draft = geo.inject_metadata(draft)
        for attempt in range(1, _GEO_RETRIES + 1):
            report = geo.audit(draft)
            if report.ok:
                print(
                    f"  [geo] Template OK — {report.question_answers} quotable Q&A block(s); "
                    f"proof numbers: {', '.join(report.found_numbers)}.",
                    flush=True,
                )
                recorder.gate("geo_gate", passed=True, attempt=attempt)
                return draft

            print(
                f"[writer] GEO template gate rejected the draft "
                f"({len(report.failures)} issue(s), attempt {attempt}/{_GEO_RETRIES}):",
                flush=True,
            )
            for failure in report.failures:
                print(f"         - {failure}", flush=True)
            recorder.gate("geo_gate", passed=False, reason=" | ".join(report.failures), attempt=attempt)

            draft = geo.inject_metadata(_run(
                self.writer_agent,
                f"{writer_prompt}\n\n{report.as_brief()}\n\nPREVIOUS DRAFT:\n{draft}",
                f"writer-{topic_id}-geo-{attempt}",
            ))

        report = geo.audit(draft)
        if not report.ok:
            raise RuntimeError(
                f"Draft still fails the GEO template after {_GEO_RETRIES} repair attempt(s): "
                + " | ".join(report.failures)
                + " — holding for human review rather than publishing a post no answer engine "
                "will quote."
            )
        # A repair pass must not buy the template by cutting the post in half.
        words = _body_word_count(draft)
        if words < MIN_BODY_WORDS:
            raise RuntimeError(
                f"GEO repair pass cut the draft to {words} words (floor is {MIN_BODY_WORDS}). "
                f"Holding for human review."
            )
        return draft

    def _run_writing_inner(self, topic_id: str, slug: str, title: str, feedback: str = "") -> dict:
        post = _get_post(topic_id)
        research_json = post.get("research_json", "{}")

        print(f"\n[writer] Writing blog post...", flush=True)
        _update_status(slug, "writing")

        # Fenced rather than interpolated raw: operator feedback is human input
        # arriving over HTTP, and it is being handed to the agent that writes to
        # the live site. See swarm/guards.py.
        fenced = guards.fence_untrusted("OPERATOR FEEDBACK", feedback)
        feedback_section = f"\n\n{fenced}" if fenced else ""
        writer_prompt = (
            f"Write a complete blog post based on this research digest:\n\n"
            f"{research_json}"
            f"{feedback_section}"
        )
        draft = _run(self.writer_agent, writer_prompt, f"writer-{topic_id}")
        draft = self._enforce_length(draft, writer_prompt, topic_id)
        draft = self._enforce_geo_template(draft, writer_prompt, topic_id)
        print(f"[writer] Draft ready ({_body_word_count(draft)} words). Running humaniser...", flush=True)

        humaniser_prompt = (
            "Humanise this draft blog post — make it sound exactly like Dhyan Karthik wrote it.\n"
            "Preserve its length: do not summarise, condense, or drop sections.\n"
            "Leave the frontmatter, every markdown table, and the first paragraph under each\n"
            "question-form (?) heading structurally intact — those are answer-engine surfaces,\n"
            "not prose to tighten. Rewrite their wording if you like; do not merge, reorder,\n"
            "shorten below 40 words, or delete them.\n\n"
            f"{draft}"
        )
        humanised = _run(self.humaniser_agent, humaniser_prompt, f"humaniser-{topic_id}")

        # The humaniser has trimmed drafts below the floor before; keep the longer text.
        if _body_word_count(humanised) < MIN_BODY_WORDS <= _body_word_count(draft):
            print(
                f"[writer] Humaniser cut {_body_word_count(draft)} → "
                f"{_body_word_count(humanised)} words; keeping the writer's draft.",
                flush=True,
            )
            humanised = draft

        # Same guard for the GEO template: the humaniser rewrites freely and has no reason to
        # respect a table or a 40-word answer block. If it broke one, the writer's draft wins.
        humanised = geo.inject_metadata(humanised)
        if not geo.audit(humanised).ok and geo.audit(draft).ok:
            print(
                "[writer] Humaniser broke the GEO template; keeping the writer's draft.",
                flush=True,
            )
            humanised = draft
        print(f"[writer] Humanised. Running imager...", flush=True)

        # Fetch topic tags for the image planner
        topic_row = _db().table("topics").select("tags").eq("id", topic_id).limit(1).execute()
        tags: list[str] = (topic_row.data[0].get("tags") or []) if topic_row.data else []
        word_count_pre = _body_word_count(humanised)

        imaged_mdx, hero_image_url, images_meta = run_imaging(
            mdx=humanised,
            slug=slug,
            title=title,
            tags=tags,
            word_count=word_count_pre,
            model=self.model,
            _run_agent_fn=_run,
            session_id=topic_id,
        )
        # Image generation happens inside the image tool, not through `_run`, so
        # it would otherwise be the one module that spends money invisibly — and
        # it is the most expensive module in the catalogue. Meter it here, from
        # what actually came back.
        image_count = len(images_meta) + (1 if hero_image_url else 0)
        if image_count:
            image_model = os.environ.get("OPENAI_IMAGE_MODEL", "dall-e-3")
            get_recorder().emit(
                "image_generator", tm.KIND_AGENT_FINISHED,
                detail={"model": image_model, "images": image_count},
                cost_usd=tm.estimate_image_cost(image_model, image_count),
            )
        print(f"[writer] Images done ({len(images_meta)} generated). Running linker...", flush=True)

        linked_mdx = run_linking(
            mdx=imaged_mdx,
            research_json=research_json,
            model=self.model,
            _run_agent_fn=_run,
            session_id=topic_id,
        )
        print(f"[writer] Links injected. Saving final draft...", flush=True)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        linked_mdx = re.sub(r'(?m)^date:.*$', f'date: "{today}"', linked_mdx, count=1)
        # `^date:` cannot match `dateModified:`, so set that one explicitly and last — the
        # imager and linker both rewrite the body after the gate ran.
        linked_mdx = geo.inject_metadata(linked_mdx, date_modified=today)

        word_count = _body_word_count(linked_mdx)

        # Extract meta from front-matter
        meta_title = title
        meta_desc = ""
        for line in linked_mdx.split("\n"):
            if line.startswith("title:"):
                meta_title = line.replace("title:", "").strip().strip('"')
            if line.startswith("description:"):
                meta_desc = line.replace("description:", "").strip().strip('"')

        # JSON-LD structured data (Article + FAQ). Best-effort — never blocks the draft.
        # The schema step also enriches the MDX frontmatter (image + faqs) so the live site,
        # which renders JSON-LD from frontmatter, emits Article + FAQPage rich results.
        schema_ld = None
        try:
            linked_mdx, schema_ld = run_schema_ld(
                mdx=linked_mdx,
                slug=slug,
                meta_title=meta_title,
                meta_description=meta_desc,
                hero_image_url=hero_image_url or "",
                model=self.model,
                _run_agent_fn=_run,
                session_id=topic_id,
            )
            word_count = _body_word_count(linked_mdx)
            if not (schema_ld or {}).get("@graph"):
                _record_step_failure(
                    topic_id, "Schema",
                    "returned no @graph — post will publish without Article/FAQPage markup",
                )
        except Exception as exc:
            _record_step_failure(topic_id, "Schema", exc)

        # Final assertion on exactly what will be published. The imager, linker and schema steps
        # all rewrite the MDX after the gate ran, so re-verify rather than assume. Cheap, and it
        # is the only check that sees the real artefact.
        final_report = geo.audit(linked_mdx)
        if not final_report.ok:
            raise RuntimeError(
                "Post-processing broke the GEO template: "
                + " | ".join(final_report.failures)
                + " — holding for human review. Suspect the imager, linker or schema step, "
                "not the writer; the draft passed the gate before they ran."
            )

        # Social kit (LinkedIn carousel + 5 post types + X threads). Best-effort — never blocks.
        social_kit: dict = {}
        try:
            social_kit = run_social(
                mdx=linked_mdx,
                research_json=research_json,
                model=self.model,
                _run_agent_fn=_run,
                session_id=topic_id,
            )
        except Exception as exc:
            _record_step_failure(topic_id, "Social", exc)

        _upsert_post(topic_id, {
            "mdx_draft": draft,
            "mdx_final": linked_mdx,
            "meta_title": meta_title,
            "meta_description": meta_desc,
            "word_count": word_count,
            "hero_image_url": hero_image_url,
            "images": json.dumps(images_meta),
            "schema_json": json.dumps(schema_ld) if schema_ld else None,
            "social_json": json.dumps(social_kit) if social_kit else None,
            "last_error": None,
        })
        _update_status(slug, "verifying_draft")
        print(f"[writer] Done. {word_count} words. Status -> verifying_draft", flush=True)
        return {"word_count": word_count, "meta_title": meta_title, "meta_description": meta_desc}

    # ── Stage: Publish ───────────────────────────────────────────────────────
    def run_publish(self, topic_id: str, slug: str) -> dict:
        post = _get_post(topic_id)
        mdx_final = post.get("mdx_final", "")
        meta_title = post.get("meta_title", slug)
        schema_json = post.get("schema_json")

        if not mdx_final:
            _mark_failed(slug, topic_id, "publish", "No mdx_final found — cannot publish.")
            raise ValueError(f"No mdx_final found for topic {slug}")

        print(f"\n[publisher] Publishing: {meta_title}", flush=True)
        _update_status(slug, "publishing")

        from swarm.tools.github_tool import github_publish
        try:
            result_raw = github_publish(slug, meta_title, mdx_final, schema_json=schema_json)
        except Exception as exc:
            print(f"[publisher] CRASH: {exc}", flush=True)
            _mark_failed(slug, topic_id, "publish", exc)
            raise

        try:
            result = json.loads(result_raw)
        except Exception:
            result = {"published": False, "error": result_raw}

        if result.get("success") or result.get("dry_run"):
            url = result.get("published_url", "(dry-run)")
            _upsert_post(topic_id, {
                "published_url": url,
                "published_at": datetime.utcnow().isoformat() + "Z",
                "last_error": None,
            })
            _update_status(slug, "published")
            print(f"[publisher] Published OK url={url}", flush=True)
            result["published"] = True
        else:
            err_msg = result.get("error", "unknown publish failure")
            print(f"[publisher] Failed: {err_msg}", flush=True)
            _mark_failed(slug, topic_id, "publish", err_msg)

        return result

    # ── Rejection handler ────────────────────────────────────────────────────
    def handle_rejection(self, topic_id: str, slug: str, current_status: str, feedback: str) -> None:
        """Re-run the appropriate stage with operator feedback.

        Feedback is sanitised here rather than at the API boundary alone, so the
        CLI path gets the same treatment as the dashboard path.
        """
        feedback = guards.sanitise_feedback(feedback)
        _db().table("blog_posts").select("rejection_log").eq("topic_id", topic_id).execute()
        post = _get_post(topic_id)
        log = post.get("rejection_log") or []
        log.append({"status": current_status, "feedback": feedback, "at": datetime.utcnow().isoformat()})
        _upsert_post(topic_id, {"rejection_log": json.dumps(log)})

        topic = _db().table("topics").select("*").eq("id", topic_id).limit(1).execute().data[0]
        title = topic["title"]
        tags = topic.get("tags", [])

        if current_status == "verifying_research":
            self.run_research(topic_id, slug, title, tags, feedback=feedback)
        elif current_status in ("verifying_draft", "scheduled"):
            # Vetoing a 'scheduled' post pulls it off the auto-publish schedule and
            # re-drafts it with feedback; it lands back at verifying_draft (a manual
            # review item) and will NOT auto-publish until you approve it.
            if current_status == "scheduled":
                _db().table("topics").update({"scheduled_for": None}).eq("id", topic_id).execute()
            self.run_writing(topic_id, slug, title, feedback=feedback)
