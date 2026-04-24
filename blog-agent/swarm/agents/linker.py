"""
LinkerAgent — injects contextual backlinks into a finished MDX blog post.

Adds 2–4 links per post:
  - 1–2 internal links to Buteforce service/blog pages (free, always)
  - 0–2 external citations to authoritative sources named in the research
"""
from __future__ import annotations
import json
from typing import Any, Callable

from google.adk.agents import LlmAgent


_INTERNAL_PAGES = {
    "ai-development": "https://www.buteforce.com/services/ai-development",
    "automation": "https://www.buteforce.com/services/automation",
    "ai agents": "https://www.buteforce.com/services/ai-development",
    "workflow": "https://www.buteforce.com/services/automation",
    "contact": "https://www.buteforce.com/contact",
}


def make_linker_agent(model: Any) -> LlmAgent:
    return LlmAgent(
        name="linker_agent",
        model=model,
        instruction="""
You are the Link Injector for Buteforce blog posts.

You receive:
1. A finished MDX blog post
2. Research data (for understanding what external sources were cited)
3. A list of already-published Buteforce blog posts (for internal blog links)
4. A list of available Buteforce service page URLs

YOUR JOB: Inject 2–4 natural, contextual hyperlinks into the post body.

LINK RULES:
- Maximum 1 link per paragraph
- Anchor text must describe the destination — never "click here", "learn more", "here", or "this"
- Do NOT link in the # title heading, the very first sentence, or the closing CTA paragraph
- Only inject links that genuinely add value to the reader
- Links should feel editorial — like a journalist citing sources, not SEO stuffing

INTERNAL LINKS (1–2, mandatory):
- Link to Buteforce service pages when the post discusses a capability Buteforce offers
  Example: if the post discusses building AI agents → link "AI development" to the service page
- Link to a published Buteforce blog post if the topic overlaps and you have its slug
  Format: [post title excerpt](https://www.buteforce.com/blog/[slug])
- Use the "available_internal_pages" list in the prompt

EXTERNAL CITATION LINKS (0–2, use only when a real authoritative source is named):
- Only link to sources explicitly named in the research data (e.g. "according to OpenAI", "McKinsey report")
- For well-known organizations, their homepage is an acceptable citation (openai.com, anthropic.com, mckinsey.com)
- Never fabricate or guess URLs for obscure sources
- Never link to competitor agencies or products

FORMAT:
- Insert links directly inline in the markdown as [anchor text](URL)
- Do NOT wrap the entire output in a code block
- Preserve all existing frontmatter, headings, and content exactly

OUTPUT: Return ONLY the complete MDX post with links injected. No preamble, no commentary.
""".strip(),
    )


def run_linking(
    mdx: str,
    research_json: str,
    model: Any,
    _run_agent_fn: Callable,
    session_id: str,
) -> str:
    """
    Inject contextual backlinks into the MDX post.
    Returns updated MDX with links embedded.
    """
    from swarm.tools.site_tool import get_published_posts

    # Fetch published posts for internal blog links
    try:
        published_raw = get_published_posts()
        published = json.loads(published_raw)
        posts_summary = [
            f"- {p.get('title', '')} → /blog/{p.get('slug', '')}"
            for p in (published.get("posts") or [])[:10]
        ]
        posts_text = "\n".join(posts_summary) if posts_summary else "None published yet."
    except Exception:
        posts_text = "Could not fetch published posts."

    # Build available internal pages list
    pages_text = "\n".join(f"- {name}: {url}" for name, url in _INTERNAL_PAGES.items())

    # Extract just the key research context (sources mentioned)
    try:
        research = json.loads(research_json)
        web_signal = research.get("source_signals", {}).get("web", "")
        key_facts = " | ".join(research.get("key_facts") or [])
        research_context = f"Web sources signal: {web_signal}\nKey facts: {key_facts}"
    except Exception:
        research_context = "Research data not available."

    linker = make_linker_agent(model)
    prompt = (
        f"=== AVAILABLE INTERNAL PAGES ===\n{pages_text}\n\n"
        f"=== PUBLISHED BUTEFORCE BLOG POSTS (for internal blog links) ===\n{posts_text}\n\n"
        f"=== RESEARCH CONTEXT (for external citation sources) ===\n{research_context}\n\n"
        f"=== MDX POST TO LINK ===\n{mdx}"
    )

    print("  [linker] Injecting backlinks...", flush=True)
    result = _run_agent_fn(linker, prompt, f"linker-{session_id}")

    # Verify the result is non-empty and looks like MDX
    if result and result.strip().startswith("---"):
        print("  [linker] Backlinks injected OK", flush=True)
        return result.strip()

    print("  [linker] Result did not look like MDX — keeping original", flush=True)
    return mdx
