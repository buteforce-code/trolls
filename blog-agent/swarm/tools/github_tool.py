"""
GitHub tool — two functions:
1. github_search(): find trending repos and issues related to a topic
2. github_publish(): commit an MDX file to the Buteforce site repo
"""
from __future__ import annotations
import os
import json
import base64
import urllib.request
import urllib.parse


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


def github_publish(slug: str, title: str, mdx_content: str) -> str:
    """
    Publish a blog post MDX file to the live Buteforce website.
    The agent now pushes content directly to the site's secure API endpoint.
    Set PUBLISH_DRY_RUN=true to simulate the publish without uploading.
    """
    site_api_url = os.environ.get("SITE_API_URL", "https://buteforce.com/api/agent/blog")
    secret_key = os.environ.get("AGENT_SECRET_KEY", "")
    dry_run = os.environ.get("PUBLISH_DRY_RUN", "true").lower() == "true"

    if dry_run:
        return json.dumps({
            "dry_run": True,
            "message": "Dry run — would have published directly to Buteforce Site",
            "would_publish_to": f"{site_api_url} (Slug: {slug})",
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
            "mdx_content": mdx_content
        }
        payload = json.dumps(payload_data).encode("utf-8")

        req = urllib.request.Request(
            site_api_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json",
                "User-Agent": "Buteforce-Blog-Agent"
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())

        return json.dumps({
            "success": True, 
            "published": True, 
            "published_url": result.get("published_url", f"https://buteforce.com/blog/{clean_slug}")
        })

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8')
        return json.dumps({"error": f"Site API Error ({e.code}): {err_msg}", "success": False, "published": False})
    except Exception as e:
        return json.dumps({"error": str(e), "success": False, "published": False})

