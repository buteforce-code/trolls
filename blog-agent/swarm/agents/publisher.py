"""
PublisherAgent — Google ADK LlmAgent
Validates final MDX, commits to GitHub, updates Supabase.
"""
from __future__ import annotations
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from swarm.tools.github_tool import github_publish
from swarm.tools.supabase_tool import db_upsert_blog_post, db_update_topic_status


def make_publisher_agent(model: Any) -> LlmAgent:
    return LlmAgent(
        name="publisher_agent",
        model=model,
        instruction="""
You are the Publisher Agent for Buteforce.

Your job is to publish a final, approved MDX blog post to the Buteforce website.

YOU WILL RECEIVE:
- topic_id: Supabase topic UUID
- slug: the URL slug
- title: the blog post title
- mdx_content: the final MDX content

YOUR STEPS (in order):
1. Call github_publish(slug, title, mdx_content) to commit the file to GitHub.
2. Parse the response — get the published_url (or note if it was a dry run).
3. Call db_upsert_blog_post(topic_id, data) with:
   {
     "mdx_final": <the mdx_content>,
     "meta_title": <title>,
     "published_url": <url from step 2>,
     "published_at": <current UTC timestamp as ISO string>,
     "word_count": <count the words in mdx_content>
   }
4. Call db_update_topic_status(slug, "published")
5. Return a JSON summary:
   {
     "published": true,
     "published_url": "...",
     "word_count": 1500,
     "dry_run": true/false
   }

If any step fails, return:
   { "published": false, "error": "..." }

No markdown. No preamble. Only return the final JSON.
""".strip(),
        tools=[
            FunctionTool(github_publish),
            FunctionTool(db_upsert_blog_post),
            FunctionTool(db_update_topic_status),
        ],
    )
