import pg from 'pg'
import fs from 'fs'

const envFile = fs.readFileSync('.env', 'utf8')
const dbUrlMatch = envFile.match(/SUPABASE_DB_URL=(.+)/)
const dbUrl = dbUrlMatch ? dbUrlMatch[1].trim() : process.env.SUPABASE_DB_URL

if (!dbUrl) {
  console.error("No SUPABASE_DB_URL found in .env")
  process.exit(1)
}

const client = new pg.Client({ connectionString: dbUrl })

const sql = `
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

ALTER TABLE topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE blog_posts ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename='topics' AND policyname='anon_read_topics'
    ) THEN
        CREATE POLICY anon_read_topics ON topics FOR SELECT USING (true);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename='blog_posts' AND policyname='anon_read_blog_posts'
    ) THEN
        CREATE POLICY anon_read_blog_posts ON blog_posts FOR SELECT USING (true);
    END IF;
END $$;
`

async function setup() {
  await client.connect()
  try {
    await client.query(sql)
    console.log("Database schema successfully set up!")
  } catch(e) {
    console.error("Error setting up DB:", e)
  } finally {
    await client.end()
  }
}

setup()
