"""
ImagerAgent — plans and generates images for a blog post.

Flow:
  1. LLM planner reads the MDX + metadata → outputs image specs as JSON
  2. For each spec: generate_and_qa (Imagen 4 + Gemini Vision gate + Supabase upload)
  3. Embed result URLs / Mermaid blocks into MDX
  4. Return (updated_mdx, hero_image_url, images_list)
"""
from __future__ import annotations
import json
from typing import Any, Callable

from google.adk.agents import LlmAgent
from swarm.agents.brand_context import _brand_context


def make_image_planner_agent(model: Any) -> LlmAgent:
    return LlmAgent(
        name="image_planner_agent",
        model=model,
        instruction=f"""
You are the Image Planner for Buteforce blog posts.

{_brand_context()}

You receive a finished blog post in MDX plus metadata: title, tags, and word count.
Your output is a JSON image spec telling the system exactly what to generate.

DECISIONS:
- Always plan exactly 1 hero image (mandatory).
- Add 0–2 inline images based on topic complexity:
  * Short posts (under 800 words) → hero only, no inline
  * Technical / systems posts → 1 architecture-style inline image
  * Opinion / strategy posts → 0 or 1 abstract inline image (only if it adds value)
  * Never force inline images where they would feel gratuitous

IMAGEN PROMPT RULES (CRITICAL — zero tolerance for text in images):
- NEVER include words, labels, numbers, arrows with text, icon labels, or any readable characters in a prompt.
- Prompts must be purely visual: describe style, composition, colors, mood, and shapes only.
- CORRECT: "abstract dark tech background, glowing electric-blue circuit traces on matte black, cinematic depth of field, 8k render, no text, no labels"
- WRONG: "diagram showing API server connecting to database with labels"
- Use Buteforce visual identity: dark backgrounds (#0a0a0a), accent colors blue/teal/violet, editorial/cinematic quality, not stock-photo.
- For architecture topics: render as abstract light/particle flows between geometric shapes — no labeled boxes.

HERO IMAGE STYLE GUIDE:
- Full-bleed cover for a B2B AI company blog
- High contrast, dark tone, editorial quality
- Subject should visually hint at the topic WITHOUT using text
- Aspect ratio: always "16:9"

INLINE IMAGE:
- Aspect ratio: "4:3"
- Complements a specific section — do not duplicate the hero mood
- placement_after_heading must be an EXACT match to an ## heading that exists in the MDX

OUTPUT — return ONLY this JSON structure, nothing else:
{{
  "hero": {{
    "prompt": "..., no text, no labels, no words",
    "alt": "Brief description for screen readers",
    "aspect_ratio": "16:9"
  }},
  "inline": [
    {{
      "type": "image",
      "placement_after_heading": "## Exact Section Heading",
      "prompt": "..., no text, no labels, no words",
      "alt": "Brief description",
      "caption": "Optional caption text or null",
      "aspect_ratio": "4:3"
    }}
  ]
}}

If no inline images are warranted, return "inline": [].
""".strip(),
    )


def _embed_hero_in_frontmatter(mdx: str, image_url: str, alt: str) -> str:
    """Add hero_image and hero_image_alt fields to the MDX frontmatter."""
    if not mdx.startswith("---"):
        return mdx

    close = mdx.find("\n---", 3)
    if close < 0:
        return mdx

    frontmatter_body = mdx[3:close]
    rest = mdx[close + 4:]

    if "hero_image:" not in frontmatter_body:
        safe_url = image_url.replace('"', "")
        safe_alt = alt.replace('"', "").replace("\n", " ")
        frontmatter_body += f'\nhero_image: "{safe_url}"\nhero_image_alt: "{safe_alt}"'

    return f"---{frontmatter_body}\n---{rest}"


def _embed_inline_image(mdx: str, spec: dict, image_url: str) -> str:
    """Insert an image block immediately after the target ## heading."""
    heading = (spec.get("placement_after_heading") or "").strip()
    if not heading:
        return mdx

    alt = spec.get("alt", "")
    caption = spec.get("caption")
    block_lines = [f"", f"![{alt}]({image_url})"]
    if caption:
        block_lines.append(f"*{caption}*")
    block = "\n".join(block_lines)

    lines = mdx.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == heading:
            lines.insert(i + 1, block)
            return "\n".join(lines)

    # Heading not found — append at end (graceful fallback)
    return mdx + f"\n{block}"


def run_imaging(
    mdx: str,
    slug: str,
    title: str,
    tags: list[str],
    word_count: int,
    model: Any,
    _run_agent_fn: Callable,
    session_id: str,
) -> tuple[str, str | None, list[dict]]:
    """
    Full imaging pipeline.
    Returns (updated_mdx, hero_image_url, images_metadata_list).
    """
    from swarm.tools.image_tool import generate_and_qa, ensure_bucket

    ensure_bucket()

    planner = make_image_planner_agent(model)
    planner_prompt = (
        f"Title: {title}\n"
        f"Tags: {', '.join(tags)}\n"
        f"Word count: {word_count}\n\n"
        f"MDX Post:\n{mdx[:4000]}"
    )

    print("  [imager] Planning image specs...", flush=True)
    raw = _run_agent_fn(planner, planner_prompt, f"img-plan-{session_id}")

    start = raw.find("{")
    end = raw.rfind("}") + 1
    try:
        specs = json.loads(raw[start:end]) if start >= 0 else {}
    except json.JSONDecodeError:
        print("  [imager] Could not parse image specs — skipping images", flush=True)
        return mdx, None, []

    updated_mdx = mdx
    hero_url: str | None = None
    images_list: list[dict] = []

    # Hero image (mandatory)
    hero = specs.get("hero") or {}
    if hero.get("prompt"):
        print("  [imager] Generating hero image...", flush=True)
        url = generate_and_qa(
            prompt=hero["prompt"],
            aspect_ratio=hero.get("aspect_ratio", "16:9"),
            slug=slug,
            image_type="hero",
        )
        if url:
            hero_url = url
            updated_mdx = _embed_hero_in_frontmatter(updated_mdx, url, hero.get("alt", title))
            images_list.append({"type": "hero", "url": url, "alt": hero.get("alt", "")})

    # Inline images (0–2)
    for idx, inline in enumerate(specs.get("inline") or [], 1):
        if not inline.get("prompt"):
            continue
        print(f"  [imager] Generating inline image {idx}...", flush=True)
        url = generate_and_qa(
            prompt=inline["prompt"],
            aspect_ratio=inline.get("aspect_ratio", "4:3"),
            slug=slug,
            image_type=f"inline-{idx}",
        )
        if url:
            updated_mdx = _embed_inline_image(updated_mdx, inline, url)
            images_list.append({"type": "inline", "url": url, "alt": inline.get("alt", "")})

    return updated_mdx, hero_url, images_list
