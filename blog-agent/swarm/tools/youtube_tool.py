"""
YouTube Data API v3 tool.
Searches for trending videos and extracts discussion signals for a topic.
"""
from __future__ import annotations
import os
import json
import urllib.request
import urllib.parse


def youtube_search(topic: str) -> str:
    """
    Search YouTube for videos about this topic.
    Returns title, channel, view count, and description snippet.
    Useful for understanding what content is performing well and why.
    """
    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        return json.dumps({"error": "YOUTUBE_API_KEY not set", "results": []})

    try:
        query = urllib.parse.urlencode({
            "part": "snippet",
            "q": topic,
            "type": "video",
            "order": "relevance",
            "maxResults": 5,
            "key": api_key,
        })
        url = f"https://www.googleapis.com/youtube/v3/search?{query}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())

        video_ids = [
            item["id"]["videoId"]
            for item in data.get("items", [])
            if item.get("id", {}).get("kind") == "youtube#video"
        ]

        # Get view counts
        stats = {}
        if video_ids:
            stats_query = urllib.parse.urlencode({
                "part": "statistics",
                "id": ",".join(video_ids),
                "key": api_key,
            })
            stats_url = f"https://www.googleapis.com/youtube/v3/videos?{stats_query}"
            with urllib.request.urlopen(stats_url, timeout=10) as resp2:
                stats_data = json.loads(resp2.read())
            for item in stats_data.get("items", []):
                vid = item["id"]
                stats[vid] = item.get("statistics", {})

        results = []
        for item in data.get("items", []):
            vid = item.get("id", {}).get("videoId", "")
            snippet = item.get("snippet", {})
            s = stats.get(vid, {})
            results.append({
                "title": snippet.get("title"),
                "channel": snippet.get("channelTitle"),
                "description": snippet.get("description", "")[:200],
                "url": f"https://youtube.com/watch?v={vid}" if vid else "",
                "view_count": s.get("viewCount", "unknown"),
                "like_count": s.get("likeCount", "unknown"),
            })

        return json.dumps({"results": results})

    except Exception as e:
        return json.dumps({"error": str(e), "results": []})
