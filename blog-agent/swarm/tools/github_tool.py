"""
GitHub tool — two functions:
1. github_search(): find trending repos and issues related to a topic
2. github_publish(): commit an MDX file to the Buteforce site repo
"""
from __future__ import annotations
import os
import json
import urllib.request
import urllib.parse
from typing import Any


def github_search(topic: str) -> str:
    """
    Search GitHub for repositories and issues related to this topic.
    Useful for understanding developer interest, open problems, and community pulse.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        query = urllib.parse.urlencode({
            "q": topic,
            "sort": "stars",
            "order": "desc",
            "per_page": 5,
        })
        url = f"https://api.github.com/search/repositories?{query}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        results = []
        for repo in data.get("items", []):
            results.append({
                "name": repo.get("full_name"),
                "description": repo.get("description", "")[:200],
                "stars": repo.get("stargazers_count"),
                "url": repo.get("html_url"),
                "language": repo.get("language"),
            })

        return json.dumps({"results": results, "total_count": data.get("total_count", 0)})

    except Exception as e:
        return json.dumps({"error": str(e), "results": []})


def github_publish(slug: str, title: str, mdx_content: str, schema_json: Any = None) -> str:
    """
    Publish a blog post MDX file to the live Buteforce website.
    The agent now pushes content directly to the site's secure API endpoint.
    Set PUBLISH_DRY_RUN=true to simulate the publish without uploading.

    schema_json (optional): JSON-LD structured data (Article + FAQ) as a dict or JSON string.
    Sent in the payload as `schema_json` so the site can inject it into the page <head>.
    """
    site_api_url = os.environ.get("SITE_API_URL", "https://www.buteforce.com/api/agent/blog")
    secret_key = os.environ.get("AGENT_SECRET_KEY", "")
    dry_run = os.environ.get("PUBLISH_DRY_RUN", "true").lower() == "true"

    if dry_run:
        return json.dumps({
            "dry_run": True,
            "message": "Dry run — would have published directly to Buteforce Site",
            "would_publish_to": f"{site_api_url} (Slug: {slug})",
            "schema_json_attached": bool(schema_json),
        })

    if not secret_key:
        return json.dumps({"error": "AGENT_SECRET_KEY not set. Cannot authenticate with Buteforce Site.", "dry_run": True})

    # Slugify: lowercase, spaces → hyphens, strip special chars
    import re
    clean_slug = re.sub(r"[^\w\s-]", "", slug.lower())
    clean_slug = re.sub(r"[\s_]+", "-", clean_slug).strip("-")[:80]

    try:
        payload_data = {
            "slug": clean_slug,
            "title": title,
            "mdx_content": mdx_content,
        }
        # Attach JSON-LD structured data if present (dict or JSON string → always send a dict).
        if schema_json:
            if isinstance(schema_json, str):
                try:
                    schema_json = json.loads(schema_json)
                except json.JSONDecodeError:
                    schema_json = None
            if schema_json:
                payload_data["schema_json"] = schema_json
        payload = json.dumps(payload_data).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
            "User-Agent": "Buteforce-Blog-Agent",
        }

        # urllib will NOT follow 307/308 for POST — it drops the body or downgrades
        # to GET — so we hop redirects ourselves while preserving method + body.
        current_url = site_api_url
        redirected_via: list[str] = []
        result: dict | None = None
        for _ in range(5):
            req = urllib.request.Request(current_url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:
                if e.code in (301, 302, 303, 307, 308):
                    location = e.headers.get("Location")
                    if not location:
                        raise
                    redirected_via.append(f"{e.code} -> {location}")
                    current_url = urllib.parse.urljoin(current_url, location)
                    continue
                raise

        if result is None:
            return json.dumps({
                "error": f"Too many redirects from {site_api_url}. Hops: {redirected_via}. "
                         f"Update SITE_API_URL to the final destination.",
                "success": False,
                "published": False,
            })

        return json.dumps({
            "success": True,
            "published": True,
            "published_url": result.get("published_url", f"https://buteforce.com/blog/{clean_slug}"),
            "redirected_via": redirected_via or None,
            "final_url": current_url if redirected_via else None,
        })

    except urllib.error.HTTPError as e:
        try:
            err_msg = e.read().decode("utf-8")
        except Exception:
            err_msg = str(e)
        return json.dumps({"error": f"Site API Error ({e.code}): {err_msg}", "success": False, "published": False})
    except Exception as e:
        return json.dumps({"error": str(e), "success": False, "published": False})

