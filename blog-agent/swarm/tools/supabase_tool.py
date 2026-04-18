"""
Supabase state management tool.
Read/write topic status and blog post artifacts.
"""
from __future__ import annotations
import os
import json
from datetime import datetime
from typing import Any

from supabase import create_client, Client


def _db() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def db_get_topic(slug: str) -> str:
    """Fetch a topic by slug. Returns JSON string."""
    try:
        result = _db().table("topics").select("*").eq("slug", slug).limit(1).execute()
        return json.dumps(result.data[0] if result.data else None)
    except Exception as e:
        return json.dumps({"error": str(e)})


def db_update_topic_status(slug: str, status: str) -> str:
    """Update topic status. Returns updated record as JSON."""
    try:
        result = (
            _db()
            .table("topics")
            .update({"status": status, "updated_at": datetime.utcnow().isoformat() + "Z"})
            .eq("slug", slug)
            .select("*")
            .execute()
        )
        return json.dumps(result.data[0] if result.data else None)
    except Exception as e:
        return json.dumps({"error": str(e)})


def db_upsert_blog_post(topic_id: str, data: dict) -> str:
    """
    Create or update blog_posts row for a topic.
    Pass a dict with any subset of: research_json, mdx_draft, mdx_final,
    meta_title, meta_description, published_url, published_at, word_count.
    """
    try:
        data["topic_id"] = topic_id
        data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        result = (
            _db()
            .table("blog_posts")
            .upsert(data, on_conflict="topic_id")
            .select("*")
            .execute()
        )
        return json.dumps(result.data[0] if result.data else None)
    except Exception as e:
        return json.dumps({"error": str(e)})


def db_get_blog_post(topic_id: str) -> str:
    """Fetch blog_posts row by topic_id."""
    try:
        result = (
            _db()
            .table("blog_posts")
            .select("*")
            .eq("topic_id", topic_id)
            .limit(1)
            .execute()
        )
        return json.dumps(result.data[0] if result.data else None)
    except Exception as e:
        return json.dumps({"error": str(e)})
