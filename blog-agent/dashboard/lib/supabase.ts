import { createClient } from '@supabase/supabase-js'

const url  = process.env.NEXT_PUBLIC_SUPABASE_URL  || process.env.SUPABASE_URL  || ''
const key  = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY || ''

export const supabase     = createClient(url, key)

// Server-only admin client (service role) — bypasses RLS. Used by /api/track to
// insert view events and by /api/stats to read the internal-only blog_views table.
// SUPABASE_SERVICE_KEY has no NEXT_PUBLIC_ prefix, so it is never shipped to the
// browser; NEVER import this into a client component.
const serviceKey = process.env.SUPABASE_SERVICE_KEY || ''
export const supabaseAdmin = createClient(
  process.env.SUPABASE_URL || url,
  serviceKey || key,
  { auth: { persistSession: false, autoRefreshToken: false } },
)
