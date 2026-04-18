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
    Commit a blog post MDX file to the Buteforce website repo (buteforce-code/ButeForce-Site).
    File is written to content/blog/{slug}.mdx — matching TinaCMS conventions.
    Set PUBLISH_DRY_RUN=true to skip the actual commit (safe default for testing).
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPO", "buteforce-code/ButeForce-Site")
    blog_path = os.environ.get("GITHUB_BLOG_PATH", "content/blog")
    branch = os.environ.get("GITHUB_BRANCH", "main")
    dry_run = os.environ.get("PUBLISH_DRY_RUN", "true").lower() == "true"

    if not token or not repo:
        return json.dumps({"error": "GITHUB_TOKEN or GITHUB_REPO not set", "dry_run": True})

    # Slugify: lowercase, spaces → hyphens, strip special chars
    import re
    clean_slug = re.sub(r"[^\w\s-]", "", slug.lower())
    clean_slug = re.sub(r"[\s_]+", "-", clean_slug).strip("-")[:80]
    filename = f"{clean_slug}.mdx"

    if dry_run:
        return json.dumps({
            "dry_run": True,
            "message": "Dry run — would have published to GitHub",
            "would_publish_to": f"https://github.com/{repo}/blob/{branch}/{blog_path}/{filename}",
        })

    try:
        api_url = f"https://api.github.com/repos/{repo}/contents/{blog_path}/{filename}"
        content_b64 = base64.b64encode(mdx_content.encode("utf-8")).decode("ascii")

        # Check if file already exists (need its SHA to update)
        sha = None
        try:
            check_req = urllib.request.Request(
                api_url,
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            with urllib.request.urlopen(check_req, timeout=10) as r:
                existing = json.loads(r.read())
                sha = existing.get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise

        payload_data: dict = {
            "message": f"feat(blog): publish — {title}",
            "content": content_b64,
            "branch": branch,
        }
        if sha:
            payload_data["sha"] = sha

        payload = json.dumps(payload_data).encode()

        req = urllib.request.Request(
            api_url,
            data=payload,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())

        html_url = result.get("content", {}).get("html_url", "")
        return json.dumps({"success": True, "published": True, "published_url": html_url})

    except Exception as e:
        return json.dumps({"error": str(e), "success": False, "published": False})
