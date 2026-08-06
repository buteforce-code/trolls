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
You are the Content Strategist for Buteforce — Precision AI Systems.
Your job: invent the NEXT batch of high-intent blog topics that compound the
brand's SEO authority across ALL of its verticals, not just one. The editorial
roadmap has been exhausted, so you must generate fresh, non-duplicate angles
grounded in what's happening now.

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
3. tavily_search_web(...)      — news, expert analysis, and data across whichever cluster the batch needs.
4. tavily_search_linkedin(...) — what buyers and practitioners are debating; real buyer language.
5. tavily_search_reddit(...)   — real pain points and questions from practitioners.
6. youtube_search(...)         — which explainers get traction (search-intent signal).
Search across ALL of Buteforce's capability areas, not just one: computer vision (QC,
defect detection, retail/construction footfall and zone analytics), document AI/OCR, AI
agents (lead qualification, inquiry handling, customer support), workflow automation, and
AI-powered web applications. The Chennai/Tamil Nadu manufacturing corridor is one real,
credible angle among these — not the default one.

━━━ STEP 3 — PROPOSE {batch} TOPICS ━━━
Return ONLY a raw JSON array (no markdown fence, no commentary) of EXACTLY {batch} objects:

[
  {{
    "title": "Punchy, SEO-rich, specific working title (contains the target keyword)",
    "target_keyword": "single primary keyword to rank for — a real, rankable long-tail",
    "tags": ["3-4", "lowercase-kebab", "taxonomy", "tags"],
    "brief": "2-3 sentences: the exact non-obvious angle, who it serves (founder/CTO/ops leader — name the vertical), and why it ranks + converts. Tie to a real signal you found.",
    "source": {{
      "platform": "one of: linkedin | reddit | youtube | news | web | search_gap | own_analysis",
      "url": "the exact URL of the thing you saw, or \\"\\" if platform is own_analysis",
      "signal": "one line: what you actually found there — the post, thread, article or query",
      "why_now": "one line: why this is timely rather than evergreen filler"
    }}
  }}
]

━━━ RULES ━━━
- SPREAD ACROSS VERTICALS. Do not let one cluster's head start crowd out the others — every
  batch should include topics from more than one capability area. The GSC SIGNALS block above
  (if present) shows what has ranked so far, but that reflects what has been published so far,
  not the whole business — treat a page-2, high-impression opportunity there as one legitimate
  target among several, not a mandate to spend the majority of every batch on it.
- Match each topic's audience and geography to what the topic is actually about — do not force
  every topic toward one region or one industry.
- ZERO duplicates: if a title overlaps an existing post or the EXISTING TITLES list, drop it and invent another.
- Each topic must serve the ICP and map to a real keyword cluster — high commercial or authority intent, no fluff.
- Prefer angles only Buteforce (a custom builder who ships production systems, not platforms) would credibly own.
- Mix intent: ~half buyer/commercial ("cost", "vs", "case study", "how to hire"), ~half authority/ecosystem.
- Do not name or reference EasyBali in any topic, title, or brief.
- EVERY topic MUST carry a truthful `source`. This is how the engine learns which kinds of
  sourcing actually produce traffic, so an invented URL poisons that measurement permanently.
  Cite the real search result you saw. If a topic came from your own reasoning rather than a
  specific find, say so honestly: platform "own_analysis" with an empty url. That is a valid,
  useful answer — a fabricated citation is not.
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


# The closed vocabulary the learning layer groups on. Free-text platforms would
# fragment into "LinkedIn"/"linkedin post"/"LI" and quietly split one arm into
# three, each too sparse to learn from.
SOURCE_PLATFORMS = {
    "linkedin", "reddit", "youtube", "news", "web", "search_gap", "own_analysis",
}
UNKNOWN_PLATFORM = "web"

_PLATFORM_HINTS = (
    ("linkedin.com", "linkedin"),
    ("reddit.com", "reddit"),
    ("youtube.com", "youtube"),
    ("youtu.be", "youtube"),
)


def _clean_source(raw: Any) -> dict:
    """Normalise the model's provenance claim into the stored shape.

    Never rejects a topic for a malformed source — an idea with murky provenance
    is still a usable idea, it just contributes nothing to the learning signal.
    Unknown platforms collapse to "web" rather than being invented into the
    vocabulary, so a typo cannot create a permanent one-observation arm.
    """
    if not isinstance(raw, dict):
        return {"platform": UNKNOWN_PLATFORM, "url": "", "signal": "", "why_now": ""}

    url = str(raw.get("url") or "").strip()[:500]
    platform = str(raw.get("platform") or "").strip().lower().replace("-", "_")

    if platform not in SOURCE_PLATFORMS:
        # Recover the platform from the URL when the label is wrong but the
        # citation is real — that combination is common and worth keeping.
        platform = next(
            (name for host, name in _PLATFORM_HINTS if host in url.lower()),
            UNKNOWN_PLATFORM,
        )

    return {
        "platform": platform,
        "url": url,
        "signal": str(raw.get("signal") or "").strip()[:500],
        "why_now": str(raw.get("why_now") or "").strip()[:500],
    }


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
            "source": _clean_source(item.get("source")),
        })
    return topics[:batch]


def run_ideation(model: Any, existing_titles: list[str], batch: int = 8,
                 db: Any | None = None) -> list[dict]:
    """Generate a batch of fresh, deduped topic dicts. Lazy-imports the shared
    ADK runner from the orchestrator to avoid a circular import at module load.

    `db` is optional: pass it to hand the agent the trend scout's pre-gated
    signals, omit it to keep the original blind-search behaviour.
    """
    from swarm.orchestrator import _run  # lazy: orchestrator is already imported by run time

    agent = make_ideator_agent(model, batch)
    titles_block = "\n".join(f"- {t}" for t in existing_titles[:200]) or "(none yet)"
    signals_block = _signals_prompt_block(db)

    prompt = (
        f"Generate {batch} NEW India-first blog topics for Buteforce.\n\n"
        f"EXISTING TITLES — already covered, do NOT duplicate or rephrase:\n{titles_block}\n\n"
        f"{signals_block}"
        f"Research first, then return ONLY the JSON array of {batch} topic objects."
    )
    raw = _run(agent, prompt, f"ideator-{int(time.time())}")
    return _extract_topics(raw, batch)


def _signals_prompt_block(db: Any | None) -> str:
    """Pre-scouted, pre-gated signals handed to the ideator.

    Without this the agent searches blind on every run and reinvents its own view
    of what is happening. The scout has already swept Hacker News, Google Trends
    and this site's own rising Search Console queries, scored each against the
    brand vocabulary, and thrown out the consumer noise — so the agent starts
    from evidence with a real URL attached rather than from a fresh guess.

    Optional by design: if the scout has never run, ideation still works exactly
    as it did before.
    """
    if db is None:
        return ""
    try:
        from swarm.trends.scout import top_signals

        signals = top_signals(db, limit=12)
    except Exception:
        return ""
    if not signals:
        return ""

    lines = ["LIVE SIGNALS — already scored and filtered for brand relevance.",
             "Prefer building topics on these; cite the one you used in `source`.",
             ""]
    for s in signals:
        lines.append(
            f"- [{s.get('score', 0):.0f} | {s.get('platform')} | {s.get('geo')}] "
            f"{(s.get('title') or '')[:110]}"
        )
        if s.get("summary"):
            lines.append(f"    {(s.get('summary') or '')[:150]}")
        if s.get("url"):
            lines.append(f"    {s['url']}")
    lines.append("")
    return "\n".join(lines)
