"""
LinkerAgent — injects contextual backlinks into a finished MDX blog post.

Adds 2–4 links per post:
  - 1–2 internal links to Buteforce service/blog pages (free, always)
  - 0–2 external citations to authoritative sources named in the research
"""
from __future__ import annotations
import json
import re
from typing import Any, Callable

from google.adk.agents import LlmAgent

from swarm.links import normalise_links, summarise

_URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+")


def _extract_urls(research: Any) -> set[str]:
    """Collect every URL appearing anywhere in the research digest."""
    return {u.rstrip(".,;") for u in _URL_RE.findall(json.dumps(research))}


# Relative, never absolute: `https://www.buteforce.com/services` costs a 308
# redirect on every click and every crawl. `swarm.links` enforces this after the
# agent runs, but the agent should be given the correct form in the first place.
_INTERNAL_PAGES = {
    "ai-development": "/services/ai-development",
    "automation": "/services/automation",
    "ai agents": "/services/ai-development",
    "workflow": "/services/automation",
    "ai audit": "/lp/ai-audit",
    "contact": "/contact",
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
- ALWAYS relative. Start with "/" — never "https://buteforce.com/..." and never
  "https://www.buteforce.com/...". An absolute link costs a redirect on every crawl.
- Link to Buteforce service pages when the post discusses a capability Buteforce offers
  Example: if the post discusses building AI agents → link "AI development" to the service page
- Link to a published Buteforce blog post ONLY if its slug appears verbatim in the
  "PUBLISHED BUTEFORCE BLOG POSTS" list below. Never guess, shorten, or reconstruct a
  slug — a slug that is not on that list does not exist and the link will 404.
  Format: [post title excerpt](/blog/[slug-copied-exactly-from-the-list])
- If that list is empty or unavailable, use service-page links only
- Use the "available_internal_pages" list in the prompt

EXTERNAL CITATION LINKS (0–2, use only when a real authoritative source is named):
- Link ONLY to a URL that appears verbatim in the research data below
- The URL must point at the specific page carrying the claim — a homepage is NOT a
  citation. "https://www.mckinsey.com" does not support a statistic; the report page does.
- If the research names a source but gives no URL, cite it in plain text and add no link
- Never fabricate, guess, or reconstruct a URL. A missing link is fine; a wrong one is not
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

    # Fetch published posts for internal blog links. `known_slugs` is the
    # allowlist the post-pass validates against, so a hallucinated slug is
    # stripped even if the agent ignores the prompt.
    known_slugs: set[str] = set()
    try:
        published_raw = get_published_posts()
        published = json.loads(published_raw)
        posts = (published.get("posts") or [])[:10]
        known_slugs = {p.get("slug", "") for p in posts if p.get("slug")}
        posts_summary = [f"- {p.get('title', '')} → /blog/{p.get('slug', '')}" for p in posts]
        posts_text = "\n".join(posts_summary) if posts_summary else "None published yet."
    except Exception:
        posts_text = "Could not fetch published posts — use service-page links only."

    # Build available internal pages list
    pages_text = "\n".join(f"- {name}: {url}" for name, url in _INTERNAL_PAGES.items())

    # Extract the research context, and the exact source URLs it surfaced —
    # only these may be cited externally.
    cited_urls: set[str] = set()
    try:
        research = json.loads(research_json)
        web_signal = research.get("source_signals", {}).get("web", "")
        key_facts = " | ".join(research.get("key_facts") or [])
        cited_urls = _extract_urls(research)
        sources_text = "\n".join(f"- {u}" for u in sorted(cited_urls)) or "No source URLs available."
        research_context = (
            f"Web sources signal: {web_signal}\nKey facts: {key_facts}\n"
            f"Source URLs you may cite (these and no others):\n{sources_text}"
        )
    except Exception:
        research_context = "Research data not available — add no external links."

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
    if not (result and result.strip().startswith("---")):
        print("  [linker] Result did not look like MDX — keeping original", flush=True)
        result = mdx

    # Deterministic pass — the prompt is advisory, this is not.
    clean, report = normalise_links(
        result.strip(), known_slugs=known_slugs, cited_urls=cited_urls
    )
    print(f"  [linker] Link check — {summarise(report)}", flush=True)
    return clean
