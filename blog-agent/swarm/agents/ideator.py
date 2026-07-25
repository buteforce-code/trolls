"""
IdeatorAgent — Google ADK LlmAgent

The autonomy refill. When the queued roadmap runs dry, this agent researches
what Buteforce has already published + what's moving in the market right now,
then proposes a fresh batch of India-first blog topics (title + target keyword +
tags + angle brief) that do NOT duplicate anything already in the pipeline.

Output is the same shape seed_topics.py uses, so the Research agent can execute
each idea exactly as if a human had seeded it.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from swarm.tools.tavily_tool import (
    tavily_search_web,
    tavily_search_linkedin,
    tavily_search_reddit,
)
from swarm.tools.youtube_tool import youtube_search
from swarm.tools.site_tool import get_published_posts, get_site_brand_data
from swarm.agents.brand_context import (
    _brand_context,
    _strategy_context,
    _seo_context,
    _signals_context,
)


def make_ideator_agent(model: Any, batch: int) -> LlmAgent:
    now = datetime.now(timezone.utc)
    current_month_year = now.strftime("%B %Y")
    return LlmAgent(
        name="ideator_agent",
        model=model,
        instruction=f"""
You are the Content Strategist for Buteforce — Chennai's Industrial AI Company.
Your job: invent the NEXT batch of high-intent blog topics that compound the
brand's India-first SEO authority. The editorial roadmap has been exhausted, so
you must generate fresh, non-duplicate angles grounded in what's happening now.

{_brand_context()}

{_strategy_context()}

{_seo_context()}

{_signals_context()}

━━━ STEP 1 — KNOW WHAT EXISTS (do this first) ━━━
1. Call get_published_posts() — read every title/angle Buteforce has already shipped.
2. Call get_site_brand_data() — services, proof stats, clients you can build topics around.
You will ALSO be handed an EXISTING TITLES list in the user message. Treat both as
"already covered — do not repeat."

━━━ STEP 2 — FIND FRESH SIGNAL ({current_month_year}) ━━━
3. tavily_search_web(...)      — India manufacturing / industrial-AI / retail-AI news, policy, data.
4. tavily_search_linkedin(...) — what Indian ops/quality/CTO leaders are debating; buyer language.
5. tavily_search_reddit(...)   — real pain points and questions from practitioners.
6. youtube_search(...)         — which explainers get traction (search-intent signal).
Search around Buteforce's clusters: computer vision QC, manufacturing defect detection,
edge AI, retail footfall/zone analytics, document AI/OCR, AI automation, n8n vs Python,
the Chennai/Tamil Nadu corridor (Hyundai, Michelin, Renault-Nissan, BMW), India-Sweden /
India-Korea corridors, IndiaAI Mission, SME manufacturing.

━━━ STEP 3 — PROPOSE {batch} TOPICS ━━━
Return ONLY a raw JSON array (no markdown fence, no commentary) of EXACTLY {batch} objects:

[
  {{
    "title": "Punchy, SEO-rich, specific working title (contains the target keyword, India-first)",
    "target_keyword": "single primary keyword to rank for — prefer an India-specific long-tail",
    "tags": ["3-4", "lowercase-kebab", "taxonomy", "tags"],
    "brief": "2-3 sentences: the exact non-obvious angle, who it serves (CTO/plant head/quality/ops/founder in India), and why it ranks + converts. Tie to a real signal you found."
  }}
]

━━━ RULES ━━━
- DOUBLE DOWN ON PROVEN DEMAND. The GSC SIGNALS block above names the clusters that already
  earn real impressions. Weight the batch toward them — until that cluster is saturated
  (10+ deep posts), at least half of every batch must extend it, using the defect-level buyer
  long-tails listed there (one named defect + one throughput number per title). Only spend the
  remainder on new authority/ecosystem angles.
- India-first, always. Never aim a topic at a US/UK/UAE/AU audience.
- ZERO duplicates: if a title overlaps an existing post or the EXISTING TITLES list, drop it and invent another.
- Each topic must serve the ICP and map to a real keyword cluster — high commercial or authority intent, no fluff.
- Prefer angles only Buteforce (a custom builder who ships on real Indian floors) would credibly own.
- Mix intent: ~half buyer/commercial ("cost", "vs", "case study", "how to hire"), ~half authority/ecosystem.
- Output MUST be valid JSON parseable by json.loads. No trailing commas. No prose outside the array.
""".strip(),
        tools=[
            FunctionTool(get_published_posts),
            FunctionTool(get_site_brand_data),
            FunctionTool(tavily_search_web),
            FunctionTool(tavily_search_linkedin),
            FunctionTool(tavily_search_reddit),
            FunctionTool(youtube_search),
        ],
    )


def _extract_topics(raw: str, batch: int) -> list[dict]:
    """Robustly pull a JSON array of topic dicts out of the agent output.
    Tolerates markdown fences and leading commentary. Returns [] on failure.
    """
    if not raw or not raw.strip():
        return []

    candidate: str | None = None
    fenced = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", raw)
    if fenced:
        candidate = fenced.group(1)
    else:
        start = raw.find("[")
        if start >= 0:
            depth = 0
            in_str = False
            esc = False
            end = -1
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
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            candidate = raw[start:end] if end > 0 else None

    if not candidate:
        return []
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []

    topics: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        if not title:
            continue
        tags = item.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        topics.append({
            "title": title,
            "target_keyword": (item.get("target_keyword") or "").strip(),
            "tags": [str(t).strip() for t in tags if str(t).strip()][:4],
            "brief": (item.get("brief") or "").strip(),
        })
    return topics[:batch]


def run_ideation(model: Any, existing_titles: list[str], batch: int = 8) -> list[dict]:
    """Generate a batch of fresh, deduped topic dicts. Lazy-imports the shared
    ADK runner from the orchestrator to avoid a circular import at module load.
    """
    from swarm.orchestrator import _run  # lazy: orchestrator is already imported by run time

    agent = make_ideator_agent(model, batch)
    titles_block = "\n".join(f"- {t}" for t in existing_titles[:200]) or "(none yet)"
    prompt = (
        f"Generate {batch} NEW India-first blog topics for Buteforce.\n\n"
        f"EXISTING TITLES — already covered, do NOT duplicate or rephrase:\n{titles_block}\n\n"
        f"Research first, then return ONLY the JSON array of {batch} topic objects."
    )
    raw = _run(agent, prompt, f"ideator-{int(time.time())}")
    return _extract_topics(raw, batch)
