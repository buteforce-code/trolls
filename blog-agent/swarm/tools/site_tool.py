"""
Site content tool — reads the Buteforce website's existing blog posts and brand data.
Used by ResearchAgent to avoid duplicate topics and align with brand voice.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path

SITE_ROOT = Path(os.environ.get("SITE_ROOT", "D:/Projects/Buteforce/Site/buteforce-website"))
BLOG_DIR  = SITE_ROOT / "content" / "blog"
DATA_FILE = SITE_ROOT / "lib" / "data.ts"


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter fields from an MDX file."""
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    fm: dict = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm


def get_published_posts() -> str:
    """
    Return a JSON list of all blog posts already published on buteforce.com.
    Each entry has: title, description, date, tags, slug.
    Use this to avoid writing about topics that have already been covered.
    """
    try:
        if not BLOG_DIR.exists():
            return json.dumps({"posts": [], "note": "Blog directory not found"})

        posts = []
        for mdx_file in sorted(BLOG_DIR.glob("*.mdx")):
            try:
                text = mdx_file.read_text(encoding="utf-8")
                fm = _parse_frontmatter(text)
                posts.append({
                    "slug": mdx_file.stem,
                    "title": fm.get("title", mdx_file.stem),
                    "description": fm.get("description", ""),
                    "date": fm.get("date", ""),
                    "tags": fm.get("tags", ""),
                })
            except Exception:
                continue

        return json.dumps({
            "total_posts": len(posts),
            "posts": posts,
            "note": "These topics are already covered — do not repeat them. Find a fresh angle or a different topic.",
        })
    except Exception as e:
        return json.dumps({"error": str(e), "posts": []})


def get_site_brand_data() -> str:
    """
    Return key brand and positioning data from the Buteforce website's lib/data.ts.
    Use this to understand the services, case studies, and proof points available.
    """
    try:
        if not DATA_FILE.exists():
            return json.dumps({"error": "data.ts not found"})

        text = DATA_FILE.read_text(encoding="utf-8")

        # Extract services section
        services: list[str] = re.findall(r'title:\s*["\']([^"\']+)["\']', text)
        stats: list[str] = re.findall(r'value:\s*["\']([^"\']+)["\']', text)
        case_studies: list[str] = re.findall(r'client:\s*["\']([^"\']+)["\']', text)

        return json.dumps({
            "services": services[:10],
            "proof_stats": stats[:8],
            "clients": case_studies[:6],
            "note": "Reference these services and proof stats in blog posts to keep content aligned with what Buteforce actually sells.",
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
