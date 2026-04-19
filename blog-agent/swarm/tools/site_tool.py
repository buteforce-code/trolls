"""
Site content tool — reads the Buteforce website's existing blog posts and brand data via API.
Used by ResearchAgent to avoid duplicate topics and align with brand voice.
"""
from __future__ import annotations
import json
import os
import urllib.request
import urllib.parse
from pathlib import Path

SITE_API_URL = os.environ.get("SITE_API_URL", "https://buteforce.com/api/agent/blog")
AGENT_SECRET_KEY = os.environ.get("AGENT_SECRET_KEY", "")


def _fetch_site_data() -> dict:
    """Helper to fetch from the Buteforce API."""
    if not AGENT_SECRET_KEY:
        # Fallback to empty if not configured (e.g. local dev missing env)
        return {"posts": [], "brand": {}}
        
    try:
        req = urllib.request.Request(SITE_API_URL, headers={
            "Authorization": f"Bearer {AGENT_SECRET_KEY}"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data
    except Exception as e:
        print(f"[site_tool] Error fetching from site API: {e}")
        return {"posts": [], "brand": {}}


def get_published_posts() -> str:
    """
    Return a JSON list of all blog posts already published on buteforce.com.
    Each entry has: title, description, slug.
    Use this to avoid writing about topics that have already been covered.
    """
    try:
        data = _fetch_site_data()
        posts = data.get("posts", [])
        
        return json.dumps({
            "total_posts": len(posts),
            "posts": posts,
            "note": "These topics are already covered — do not repeat them. Find a fresh angle or a different topic.",
        })
    except Exception as e:
        return json.dumps({"error": str(e), "posts": []})


def get_site_brand_data() -> str:
    """
    Return key brand and positioning data from the Buteforce website.
    Use this to understand the services, case studies, and proof points available.
    """
    try:
        data = _fetch_site_data()
        brand = data.get("brand", {})
        
        return json.dumps({
            "services": brand.get("services", [])[:10],
            "proof_stats": brand.get("proof_stats", [])[:8],
            "clients": brand.get("clients", [])[:6],
            "note": "Reference these services and proof stats in blog posts to keep content aligned with what Buteforce actually sells.",
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
