"""
SocialAgent — repurposes a finished blog post into a platform-native social kit.

The 2026 strategy's content-repurposing chain is: blog post -> LinkedIn carousel -> X thread ->
single tweet -> LinkedIn company-page post. This agent runs that chain in one structured pass,
producing India-first content in Dhyan's founder voice, using the strategy's exact post types and
hashtag groups (Marketing strategy §5 LinkedIn, §6 Twitter/X).

Best-effort: never blocks the pipeline. Returns a dict persisted to blog_posts.social_json so the
dashboard / operator can copy each asset out. Empty dict on failure.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

from google.adk.agents import LlmAgent

from swarm.agents.brand_context import _brand_context, _strategy_context


def _extract_json(raw: str) -> dict:
    """Pull the first balanced JSON object out of the model output. {} on failure."""
    if not raw or not raw.strip():
        return {}
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw)
    candidate = fenced.group(1) if fenced else None
    if not candidate:
        start = raw.find("{")
        if start < 0:
            return {}
        depth = 0
        in_str = esc = False
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
    except json.JSONDecodeError:
        return {}


def make_social_agent(model: Any) -> LlmAgent:
    return LlmAgent(
        name="social_agent",
        model=model,
        instruction=f"""
You are the Social Repurposing Agent for Buteforce — Chennai's Industrial AI Company.

{_brand_context()}

{_strategy_context()}

You receive a finished blog post (MDX) and its research digest. Turn that ONE post into a
platform-native social kit for LinkedIn and X, written in Dhyan Karthik's founder voice:
direct, technically grounded, India-first, anti-fluff. Every asset must be specific to THIS post —
real numbers and angles from it, never generic "AI is changing everything" filler.

PLATFORM RULES (2026):
- LinkedIn rewards founder-voice, debate, and carousels. First-person. No corporate tone.
- Put external links in the FIRST COMMENT, never in the post body (in-body links cut reach ~40%).
- X/Twitter is for the technical + ecosystem audience: developers, journalists, IndiaAI/NASSCOM.
- Bilateral content (SITAC / IndiaAI / India-Sweden / India-Korea) only when the post genuinely
  relates to the corridor; otherwise set "bilateral" to "" (empty string).

Output ONLY this raw JSON object. No markdown fences, no commentary.

{{
  "linkedin": {{
    "founder_story": "Type 1 — first-person story post. Hook format 'I [did X]. Here's what I learned:' Real technical + emotional. 120-200 words. Line breaks between short paragraphs.",
    "contrarian": "Type 2 — a contrarian take that invites debate (comments = reach). 80-150 words. Must be defensible, not clickbait.",
    "data_post": "Type 3 — one counterintuitive number from the post + explanation + takeaway. 80-150 words.",
    "bilateral": "Type 4 — corridor/ecosystem angle for officials (SITAC/IndiaAI/Business Sweden/NASSCOM). 100-160 words. EMPTY STRING if the post is not corridor-related.",
    "company_page": "Buteforce company-page repost: one number, one outcome, one CTA. 40-80 words.",
    "carousel": {{
      "title": "Carousel hook title",
      "slides": ["Slide 1 (cover/hook)", "Slide 2", "Slide 3", "Slide 4", "Slide 5", "Slide 6"]
    }}
  }},
  "x": {{
    "thread_numbered": ["1/ hook tweet", "2/ ...", "3/ ...", "4/ ...", "5/ ..."],
    "thread_story_or_howto": ["opening tweet", "...", "...", "...", "closing tweet with soft CTA"],
    "tweets": ["standalone tweet 1 (a stat from the post)", "standalone tweet 2 (a build-in-public observation)"]
  }},
  "hashtags": {{
    "linkedin": ["#IndustrialAI", "#ComputerVision", "#ManufacturingAI", "plus 2-3 relevant from: #Chennai #IndiaAI #AIautomation #MachineVision #RetailAnalytics #EdgeAI #YOLOv8 #Hooter"],
    "x": ["3-5 relevant tags, e.g. #IndustrialAI #ComputerVision #IndiaAI #EdgeAI"]
  }},
  "first_comment_link": "Suggested first-comment text containing the blog URL, e.g. 'Full breakdown on the blog: <link>'"
}}

QUALITY RULES:
- Carousel: 5-7 slides, each slide one tight idea (a phrase or 1-2 short sentences), not a paragraph.
- Threads: each tweet under ~270 chars. Numbered thread is for reach; story/how-to is for replies/bookmarks.
- Keep India / Chennai / manufacturing-corridor context where the post supports it.
- No banned filler: "leveraging", "game-changing", "seamless", "synergy", "In conclusion", "It's worth noting".
""".strip(),
    )


def run_social(
    mdx: str,
    research_json: str,
    model: Any,
    _run_agent_fn: Callable,
    session_id: str,
) -> dict:
    """Generate the LinkedIn + X social kit for a finished post. {} on any failure (never raises)."""
    agent = make_social_agent(model)
    prompt = (
        f"=== RESEARCH DIGEST ===\n{research_json}\n\n"
        f"=== FINISHED BLOG POST (MDX) ===\n{mdx[:9000]}"
    )
    try:
        print("  [social] Generating LinkedIn + X kit...", flush=True)
        raw = _run_agent_fn(agent, prompt, f"social-{session_id}")
    except Exception as exc:
        print(f"  [social] Generation failed (non-fatal): {exc}", flush=True)
        return {}

    kit = _extract_json(raw)
    if kit.get("linkedin") or kit.get("x"):
        n_slides = len((kit.get("linkedin", {}).get("carousel", {}) or {}).get("slides", []) or [])
        print(f"  [social] Kit ready (carousel {n_slides} slides, "
              f"{len(kit.get('x', {}).get('thread_numbered', []) or [])}-tweet thread).", flush=True)
        return kit
    print("  [social] No usable kit parsed; skipping.", flush=True)
    return {}
