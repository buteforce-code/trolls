"""Analytics ingestion — the engine's feedback channel.

Pulls what actually happened in search (Google Search Console) and on the page
(GA4) back into Supabase, keyed by post slug, so the swarm can be scored on
outcomes instead of on intent.
"""
