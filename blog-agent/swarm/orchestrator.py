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


def _get_post(topic_id: str) -> dict:
    r = _db().table("blog_posts").select("*").eq("topic_id", topic_id).limit(1).execute()
    return r.data[0] if r.data else {}


# ── ADK runner ───────────────────────────────────────────────────────────────
async def _run_agent(agent: LlmAgent, prompt: str, session_id: str, retries: int = 3) -> str:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            svc = InMemorySessionService()
            session = await svc.create_session(
                app_name=agent.name, user_id="dhyan", session_id=f"{session_id}-{attempt}"
            )
            runner = Runner(agent=agent, app_name=agent.name, session_service=svc)
            content = genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])
            parts: list[str] = []
            async for event in runner.run_async(user_id="dhyan", session_id=session.id, new_message=content):
                if hasattr(event, "content") and event.content:
                    for p in event.content.parts:
                        if hasattr(p, "text") and p.text:
                            parts.append(p.text)
            return "".join(parts).strip()
        except Exception as exc:
            last_err = exc
            msg = str(exc).lower()
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
            # "overloaded", "service unavailable") and Gemini (503/UNAVAILABLE).
            is_unavailable = (
                "503" in msg or "502" in msg or "500" in msg
                or "unavailable" in msg or "overloaded" in msg
                or "high demand" in msg or "timeout" in msg
                or "timed out" in msg or "apiconnection" in msg
            )
            if (is_quota or is_unavailable) and attempt < retries - 1:
                wait = 20 * (attempt + 1)
                reason = "Quota" if is_quota else "Model unavailable (503)"
                print(f"  [WAIT] {reason}, retrying in {wait}s...", flush=True)
                await asyncio.sleep(wait)
            else:
                break
    raise RuntimeError(f"Agent '{agent.name}' failed after {retries} attempts: {last_err}")


def _run(agent: LlmAgent, prompt: str, session_id: str) -> str:
    return asyncio.run(_run_agent(agent, prompt, session_id))


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

    def run_research(self, topic_id: str, slug: str, title: str, tags: list[str]) -> dict:
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

        prompt = (
            f"Research this topic thoroughly using all available tools:\n\n"
            f"Topic: {title}\nTags: {', '.join(tags)}"
            f"{roadmap_section}"
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

    def _run_writing_inner(self, topic_id: str, slug: str, title: str, feedback: str = "") -> dict:
        post = _get_post(topic_id)
        research_json = post.get("research_json", "{}")

        print(f"\n[writer] Writing blog post...", flush=True)
        _update_status(slug, "writing")

        feedback_section = f"\n\nOPERATOR FEEDBACK TO INCORPORATE:\n{feedback}" if feedback else ""
        writer_prompt = (
            f"Write a complete blog post based on this research digest:\n\n"
            f"{research_json}"
            f"{feedback_section}"
        )
        draft = _run(self.writer_agent, writer_prompt, f"writer-{topic_id}")
        print(f"[writer] Draft ready ({len(draft.split())} words). Running humaniser...", flush=True)

        humaniser_prompt = (
            f"Humanise this draft blog post — make it sound exactly like Dhyan Karthik wrote it:\n\n{draft}"
        )
        humanised = _run(self.humaniser_agent, humaniser_prompt, f"humaniser-{topic_id}")
        print(f"[writer] Humanised. Running imager...", flush=True)

        # Fetch topic tags for the image planner
        topic_row = _db().table("topics").select("tags").eq("id", topic_id).limit(1).execute()
        tags: list[str] = (topic_row.data[0].get("tags") or []) if topic_row.data else []
        word_count_pre = len(humanised.split())

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

        word_count = len(linked_mdx.split())

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
            word_count = len(linked_mdx.split())
        except Exception as exc:
            print(f"[writer] Schema generation failed (non-fatal): {exc}", flush=True)

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
            print(f"[writer] Social generation failed (non-fatal): {exc}", flush=True)

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
        """Re-run the appropriate stage with operator feedback."""
        _db().table("blog_posts").select("rejection_log").eq("topic_id", topic_id).execute()
        post = _get_post(topic_id)
        log = post.get("rejection_log") or []
        log.append({"status": current_status, "feedback": feedback, "at": datetime.utcnow().isoformat()})
        _upsert_post(topic_id, {"rejection_log": json.dumps(log)})

        topic = _db().table("topics").select("*").eq("id", topic_id).limit(1).execute().data[0]
        title = topic["title"]
        tags = topic.get("tags", [])

        if current_status == "verifying_research":
            self.run_research(topic_id, slug, title, tags)
        elif current_status in ("verifying_draft", "scheduled"):
            # Vetoing a 'scheduled' post pulls it off the auto-publish schedule and
            # re-drafts it with feedback; it lands back at verifying_draft (a manual
            # review item) and will NOT auto-publish until you approve it.
            if current_status == "scheduled":
                _db().table("topics").update({"scheduled_for": None}).eq("id", topic_id).execute()
            self.run_writing(topic_id, slug, title, feedback=feedback)
