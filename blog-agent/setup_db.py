"""
Supabase schema bootstrap — idempotent.
Run: python setup_db.py
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

STATEMENTS = [
    # topics table
    """
    CREATE TABLE IF NOT EXISTS topics (
        id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        slug        text UNIQUE NOT NULL,
        title       text NOT NULL,
        status      text NOT NULL DEFAULT 'queued',
        tags        text[] DEFAULT '{}',
        created_at  timestamptz DEFAULT now(),
        updated_at  timestamptz DEFAULT now()
    )
    """,
    # blog_posts table
    """
    CREATE TABLE IF NOT EXISTS blog_posts (
        id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        topic_id            uuid REFERENCES topics(id) ON DELETE CASCADE,
        research_json       text,
        mdx_draft           text,
        mdx_final           text,
        meta_title          text,
        meta_description    text,
        published_url       text,
        published_at        timestamptz,
        word_count          int DEFAULT 0,
        rejection_log       jsonb DEFAULT '[]',
        created_at          timestamptz DEFAULT now(),
        updated_at          timestamptz DEFAULT now()
    )
    """,
    # Image columns (idempotent — safe to re-run)
    "ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS hero_image_url text",
    "ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS images jsonb DEFAULT '[]'",
    # RLS — service key bypasses, anon key reads
    "ALTER TABLE topics ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE blog_posts ENABLE ROW LEVEL SECURITY",
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies WHERE tablename='topics' AND policyname='anon_read_topics'
        ) THEN
            CREATE POLICY anon_read_topics ON topics FOR SELECT USING (true);
        END IF;
    END $$
    """,
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies WHERE tablename='blog_posts' AND policyname='anon_read_blog_posts'
        ) THEN
            CREATE POLICY anon_read_blog_posts ON blog_posts FOR SELECT USING (true);
        END IF;
    END $$
    """,
]

if __name__ == "__main__":
    print("Setting up Supabase schema...")
    for i, stmt in enumerate(STATEMENTS):
        clean = stmt.strip()
        if not clean:
            continue
        try:
            supabase.rpc("exec_sql", {"sql": clean}).execute()
            print(f"  [{i+1}/{len(STATEMENTS)}] OK")
        except Exception as e:
            err = str(e)
            if "already exists" in err or "duplicate" in err.lower():
                print(f"  [{i+1}/{len(STATEMENTS)}] SKIP (already exists)")
            else:
                print(f"  [{i+1}/{len(STATEMENTS)}] ERROR: {err}")

    print("\nDone. Verifying tables...")
    try:
        r1 = supabase.table("topics").select("id").limit(1).execute()
        r2 = supabase.table("blog_posts").select("id").limit(1).execute()
        print("  ✓ topics table accessible")
        print("  ✓ blog_posts table accessible")
    except Exception as e:
        print(f"  ✗ Verification failed: {e}")
        print("  → Run the SQL manually in Supabase SQL Editor:")
        print("""
    CREATE TABLE IF NOT EXISTS topics (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        slug text UNIQUE NOT NULL,
        title text NOT NULL,
        status text NOT NULL DEFAULT 'queued',
        tags text[] DEFAULT '{}',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS blog_posts (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        topic_id uuid REFERENCES topics(id) ON DELETE CASCADE,
        research_json text,
        mdx_draft text,
        mdx_final text,
        meta_title text,
        meta_description text,
        published_url text,
        published_at timestamptz,
        word_count int DEFAULT 0,
        rejection_log jsonb DEFAULT '[]',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    );
        """)
