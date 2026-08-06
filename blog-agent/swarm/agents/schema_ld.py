"""
SchemaAgent — generates JSON-LD structured data for a finished blog post.

The Buteforce site renders blog posts from MDX frontmatter (gray-matter) and already emits an
Article JSON-LD from it. The cheapest big SEO win is therefore to enrich that frontmatter so the
site can also emit FAQPage rich results and an Article `image`:

  - `image` — the hero image URL, so the Article schema carries an image (Google rich result requirement).
  - `faqs`  — a list of {question, answer} the site renders as FAQPage JSON-LD.

This step returns the MDX with those frontmatter keys injected (committed + rendered by the site) AND
a detached JSON-LD `@graph` (BlogPosting + FAQPage) that is persisted to blog_posts.schema_json for the
dashboard / debugging. We do NOT inject JSON-LD into the MDX *body* — JSON braces break MDX/JSX parsing.
The function never raises; on any failure it returns the MDX unchanged and at least the Article node.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Callable

from swarm import brand

# The entity this markup asserts is per-tenant, and it is the highest-stakes thing the swarm
# emits: AI Visibility SCAN 001 found an entity gap — not a content gap — was the root cause of
# 0/18 citations. One spelling of the author everywhere, or a knowledge graph sees two people.
# (This module once said "Dhyan Karthik" while the live site rendered "Dhyaneshwaran".) Those
# values now come from the active `BrandProfile`, so a second tenant asserts its own entity
# rather than inheriting ours.
#
# Module-level `SITE` / `AUTHOR` / `AUTHOR_ID` / `AUTHOR_URL` / `ORG` still resolve, lazily,
# for any caller that reads them.
_PROFILE_BACKED: dict[str, str] = {
    "SITE": "site_url",
    "AUTHOR": "author_name",
    "AUTHOR_ID": "author_id",
    "AUTHOR_URL": "author_url",
    "ORG": "name",
}


def __getattr__(name: str):
    path = _PROFILE_BACKED.get(name)
    if path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(brand.active(), path)


def _parse_frontmatter(mdx: str) -> dict:
    """Extract the YAML-ish frontmatter block between the first pair of `---` fences."""
    out: dict = {}
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n", mdx, flags=re.DOTALL)
    if not m:
        return out
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            items = re.findall(r'"([^"]*)"|\'([^\']*)\'|([^,\[\]]+)', val[1:-1])
            out[key] = [next(s for s in t if s).strip() for t in items if any(s.strip() for s in t)]
        else:
            out[key] = val.strip().strip('"').strip("'")
    return out


def _inject_frontmatter(mdx: str, extra: dict[str, Any]) -> str:
    """Append keys to the MDX frontmatter as JSON-flow YAML (valid YAML, parsed by js-yaml/gray-matter).

    JSON is a strict subset of YAML, so one-line `key: <json>` avoids multi-line indentation pitfalls.
    Existing keys are not overwritten.
    """
    if not extra:
        return mdx
    m = re.match(r"^(\s*---\s*\n)(.*?)(\n---\s*\n)(.*)$", mdx, flags=re.DOTALL)
    if not m:
        return mdx
    head, fm, close, body = m.groups()
    lines = []
    for key, value in extra.items():
        if re.search(rf"(?m)^{re.escape(key)}\s*:", fm):
            continue  # do not clobber an existing key
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    if not lines:
        return mdx
    return f"{head}{fm}\n" + "\n".join(lines) + f"{close}{body}"


def _extract_faqs(
    body: str, model: Any, _run_agent_fn: Callable, session_id: str,
) -> list[dict]:
    """Ask the model for 3-5 reader questions the post answers. Best-effort; [] on any failure.

    Returns simple [{"question": str, "answer": str}] pairs.
    """
    from google.adk.agents import LlmAgent

    agent = LlmAgent(
        name="schema_faq_agent",
        model=model,
        instruction="""
You generate FAQ structured data from a blog post.

Read the post and produce 3 to 5 question/answer pairs that a real reader (an Indian manufacturing
or retail decision-maker) would search for and that THIS POST actually answers. Answers must be
self-contained, factual, drawn only from the post, and 1-3 sentences each.

Output ONLY a raw JSON array. No markdown fences, no commentary. Exactly this shape:
[
  {"question": "...", "answer": "..."},
  {"question": "...", "answer": "..."}
]
""".strip(),
    )
    try:
        raw = _run_agent_fn(agent, f"POST:\n\n{body[:9000]}", f"schema-faq-{session_id}")
    except Exception as exc:
        print(f"  [schema] FAQ extraction failed ({exc}); Article-only.", flush=True)
        return []

    m = re.search(r"\[\s*{.*}\s*\]", raw, flags=re.DOTALL)
    if not m:
        return []
    try:
        pairs = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []

    faqs = []
    for p in pairs:
        if not isinstance(p, dict):
            continue
        q = (p.get("question") or "").strip()
        a = (p.get("answer") or "").strip()
        if q and a:
            faqs.append({"question": q, "answer": a})
    return faqs[:5]


def _article_node(
    *, slug: str, title: str, description: str, date: str, date_modified: str,
    tags: list[str], hero_image_url: str,
) -> dict:
    p = brand.active()
    site = p.site_url.rstrip("/")

    author: dict[str, Any] = {"@type": "Person", "name": p.author_name}
    if p.author_id:
        author["@id"] = p.author_id
    if p.author_job_title:
        author["jobTitle"] = p.author_job_title
    if p.author_url:
        author["url"] = p.author_url
    author["worksFor"] = {"@type": "Organization", "name": p.name, "url": site}

    publisher: dict[str, Any] = {"@type": "Organization", "name": p.name, "url": site}
    if p.logo_url:
        publisher["logo"] = {"@type": "ImageObject", "url": p.logo_url}

    node: dict[str, Any] = {
        "@type": "BlogPosting",
        "headline": title[:110],
        "description": description,
        "datePublished": date,
        "dateModified": date_modified or date,
        "author": author,
        "publisher": publisher,
        "mainEntityOfPage": {"@type": "WebPage", "@id": f"{site}/blog/{slug}"},
        "url": f"{site}/blog/{slug}",
        "inLanguage": p.content_locale,
    }
    if hero_image_url:
        node["image"] = hero_image_url
    if tags:
        node["keywords"] = ", ".join(tags)
    return node


def run_schema_ld(
    *,
    mdx: str,
    slug: str,
    meta_title: str,
    meta_description: str,
    hero_image_url: str,
    model: Any,
    _run_agent_fn: Callable,
    session_id: str,
) -> tuple[str, dict]:
    """Enrich the MDX frontmatter (image, faqs) and build the JSON-LD @graph.

    Returns (mdx_out, schema_graph). Never raises — on failure returns (mdx, {Article-only graph}).
    """
    fm = _parse_frontmatter(mdx)
    title = meta_title or fm.get("title") or slug.replace("-", " ").title()
    description = meta_description or fm.get("description") or ""
    date = fm.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_modified = fm.get("dateModified") or date
    tags = fm.get("tags") if isinstance(fm.get("tags"), list) else []

    graph: list[dict] = [_article_node(
        slug=slug, title=title, description=description,
        date=date, date_modified=date_modified, tags=tags, hero_image_url=hero_image_url,
    )]

    # Body without frontmatter for FAQ extraction.
    body = re.sub(r"^\s*---\s*\n.*?\n---\s*\n", "", mdx, count=1, flags=re.DOTALL)
    faqs = _extract_faqs(body, model, _run_agent_fn, session_id)
    if faqs:
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f["question"],
                    "acceptedAnswer": {"@type": "Answer", "text": f["answer"]},
                }
                for f in faqs
            ],
        })
        print(f"  [schema] Article + FAQPage ({len(faqs)} Q&A) generated.", flush=True)
    else:
        print("  [schema] Article JSON-LD generated (no FAQ).", flush=True)

    # Push image + faqs into the frontmatter so the live site renders them.
    extra: dict[str, Any] = {}
    if hero_image_url:
        extra["image"] = hero_image_url
    if faqs:
        extra["faqs"] = faqs
    mdx_out = _inject_frontmatter(mdx, extra)

    return mdx_out, {"@context": "https://schema.org", "@graph": graph}
