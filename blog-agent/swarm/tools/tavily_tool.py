"""
Tavily multi-source search tool.
Searches X, Reddit, LinkedIn, Instagram, general web via Tavily API.
Used by ResearchAgent.
"""
from __future__ import annotations
import os
import json
from typing import Any

try:
    from tavily import TavilyClient
    _TAVILY_AVAILABLE = True
except ImportError:
    _TAVILY_AVAILABLE = False


def _get_client() -> Any:
    key = os.environ.get("TAVILY_API_KEY", "")
    if not key or not _TAVILY_AVAILABLE:
        return None
    return TavilyClient(api_key=key)


def tavily_search_web(topic: str) -> str:
    """
    Broad web search for a topic. Returns top results as JSON string.
    Covers news, blogs, industry analysis.
    """
    client = _get_client()
    if not client:
        return json.dumps({"error": "Tavily not available", "results": []})
    try:
        resp = client.search(
            query=f"{topic} 2024 2025",
            search_depth="advanced",
            max_results=6,
            include_answer=True,
        )
        return json.dumps({
            "answer": resp.get("answer", ""),
            "results": [
                {"title": r.get("title"), "url": r.get("url"), "content": r.get("content", "")[:400]}
                for r in resp.get("results", [])
            ],
        })
    except Exception as e:
        return json.dumps({"error": str(e), "results": []})


def tavily_search_x(topic: str) -> str:
    """
    Search X (Twitter) for discussions about this topic.
    Returns threads, opinions, hot takes.
    """
    client = _get_client()
    if not client:
        return json.dumps({"error": "Tavily not available", "results": []})
    try:
        resp = client.search(
            query=f"site:x.com OR site:twitter.com {topic}",
            search_depth="advanced",
            max_results=5,
            include_answer=False,
        )
        return json.dumps({
            "results": [
                {"title": r.get("title"), "url": r.get("url"), "content": r.get("content", "")[:300]}
                for r in resp.get("results", [])
            ],
        })
    except Exception as e:
        return json.dumps({"error": str(e), "results": []})


def tavily_search_reddit(topic: str) -> str:
    """
    Search Reddit for threads, discussions, and community sentiment about this topic.
    """
    client = _get_client()
    if not client:
        return json.dumps({"error": "Tavily not available", "results": []})
    try:
        resp = client.search(
            query=f"site:reddit.com {topic}",
            search_depth="advanced",
            max_results=5,
            include_answer=False,
        )
        return json.dumps({
            "results": [
                {"title": r.get("title"), "url": r.get("url"), "content": r.get("content", "")[:300]}
                for r in resp.get("results", [])
            ],
        })
    except Exception as e:
        return json.dumps({"error": str(e), "results": []})


def tavily_search_linkedin(topic: str) -> str:
    """
    Search LinkedIn for professional perspectives, articles, and thought leadership on this topic.
    """
    client = _get_client()
    if not client:
        return json.dumps({"error": "Tavily not available", "results": []})
    try:
        resp = client.search(
            query=f"site:linkedin.com {topic}",
            search_depth="advanced",
            max_results=5,
            include_answer=False,
        )
        return json.dumps({
            "results": [
                {"title": r.get("title"), "url": r.get("url"), "content": r.get("content", "")[:300]}
                for r in resp.get("results", [])
            ],
        })
    except Exception as e:
        return json.dumps({"error": str(e), "results": []})


def tavily_search_instagram(topic: str) -> str:
    """
    Search Instagram for public posts and creator content related to this topic.
    """
    client = _get_client()
    if not client:
        return json.dumps({"error": "Tavily not available", "results": []})
    try:
        resp = client.search(
            query=f"site:instagram.com {topic}",
            search_depth="basic",
            max_results=4,
            include_answer=False,
        )
        return json.dumps({
            "results": [
                {"title": r.get("title"), "url": r.get("url"), "content": r.get("content", "")[:200]}
                for r in resp.get("results", [])
            ],
        })
    except Exception as e:
        return json.dumps({"error": str(e), "results": []})
