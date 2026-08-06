"""Deterministic link hygiene for finished MDX posts.

The linker agent is an LLM, so its link rules are advisory. This module enforces
them after the fact, which is what actually keeps published posts clean:

  1. Internal links are relative. `https://www.buteforce.com/services` is a 308
     redirect hop on every click and every crawl; `/services` is not.
  2. Internal `/blog/<slug>` links must point at a slug that really exists.
  3. External links must be a URL the research actually surfaced, and must not
     be a bare homepage — `mckinsey.com` is not evidence for a specific stat.

Anything failing 2 or 3 is *unwrapped*, not deleted: `[text](bad-url)` becomes
`text`, so the prose survives intact and only the false link is removed.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from swarm import brand

# Inline markdown link, excluding image embeds (which are `![alt](src)`).
_LINK_RE = re.compile(r"(?<!!)\[([^\]\[]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_FRONTMATTER_RE = re.compile(r"\A(---\n.*?\n---\n)", re.DOTALL)


def _internal_hosts() -> frozenset[str]:
    """Hosts that count as this tenant's own, so a link to them is rewritten relative.

    Derived from the active `BrandProfile` (which adds the `www.` twin automatically) rather
    than hardcoded, so a second tenant does not treat buteforce.com as its own site — and,
    worse, leave its own absolute URLs un-rewritten and paying a 308 on every crawl.
    """
    return brand.active().hosts

# Static site paths the linker is allowed to target.
KNOWN_PATHS = frozenset({
    "/", "/services", "/work", "/blog", "/about", "/contact", "/faq",
    "/lp/ai-audit", "/services/ai-development", "/services/automation",
})


def _split_frontmatter(mdx: str) -> tuple[str, str]:
    match = _FRONTMATTER_RE.match(mdx)
    return (match.group(1), mdx[match.end():]) if match else ("", mdx)


def _to_relative(url: str) -> str:
    """Rewrite an absolute Buteforce URL to a site-relative path."""
    parsed = urlparse(url)
    if parsed.netloc.lower() in _internal_hosts():
        path = parsed.path or "/"
        return f"{path}#{parsed.fragment}" if parsed.fragment else path
    return url


def _is_homepage(url: str) -> bool:
    """True when the URL carries no path — a homepage cannot source a claim."""
    parsed = urlparse(url)
    return parsed.path.strip("/") == "" and not parsed.query


def _internal_path_ok(path: str, known_slugs: set[str]) -> bool:
    bare = path.split("#", 1)[0].rstrip("/") or "/"
    if bare in KNOWN_PATHS:
        return True
    if bare.startswith("/blog/"):
        return bare[len("/blog/"):] in known_slugs
    return False


def normalise_links(
    mdx: str,
    *,
    known_slugs: set[str] | None = None,
    cited_urls: set[str] | None = None,
) -> tuple[str, dict[str, list[str]]]:
    """Return `(clean_mdx, report)` with every link rule enforced.

    `known_slugs` are the slugs of genuinely published posts; `cited_urls` are
    the external URLs the research digest actually surfaced. When `cited_urls`
    is empty the external-source check is skipped, so a research fetch failure
    degrades to "leave external links alone" rather than stripping all of them.
    """
    known_slugs = known_slugs or set()
    cited_urls = cited_urls or set()
    cited_hosts = {urlparse(u).netloc.lower().removeprefix("www.") for u in cited_urls if u}

    report: dict[str, list[str]] = {
        "rewritten_absolute": [],
        "phantom_internal": [],
        "homepage_citations": [],
        "uncited_external": [],
    }

    frontmatter, body = _split_frontmatter(mdx)

    def _replace(match: re.Match[str]) -> str:
        text, url = match.group(1), match.group(2)

        relative = _to_relative(url)
        if relative != url:
            report["rewritten_absolute"].append(url)
            url = relative

        if url.startswith("/"):
            if not _internal_path_ok(url, known_slugs):
                report["phantom_internal"].append(url)
                return text
            return f"[{text}]({url})"

        if url.startswith(("#", "mailto:", "tel:")):
            return f"[{text}]({url})"

        if _is_homepage(url):
            report["homepage_citations"].append(url)
            return text

        host = urlparse(url).netloc.lower().removeprefix("www.")
        if cited_hosts and host not in cited_hosts:
            report["uncited_external"].append(url)
            return text

        return f"[{text}]({url})"

    return frontmatter + _LINK_RE.sub(_replace, body), report


def summarise(report: dict[str, list[str]]) -> str:
    """One-line human summary of what was changed, for pipeline logs."""
    parts = [f"{name.replace('_', ' ')}: {len(urls)}" for name, urls in report.items() if urls]
    return "; ".join(parts) if parts else "no link defects"
