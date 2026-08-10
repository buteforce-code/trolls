import { createClient, type SupabaseClient } from '@supabase/supabase-js'

/**
 * Server-only admin client (service role) — bypasses RLS. Used by /api/track to
 * insert view events, /api/stats to read the internal-only blog_views table, and
 * the swarm/learning routes whose anon read policies were dropped.
 * SUPABASE_SERVICE_KEY has no NEXT_PUBLIC_ prefix, so it is never shipped to the
 * browser; NEVER import this into a client component.
 *
 * The connection is opened on first use rather than at import time. `next build`
 * imports every route module to collect its config, so a client constructed at
 * module scope runs during the build — where runtime secrets do not exist. On
 * Railway they are absent even when set on the service, because a Dockerfile
 * only receives the build args it declares with ARG. Declaring them would also
 * bake the service key into an image layer, where `docker history` can read it.
 * Deferring the connection keeps the build independent of runtime config and
 * keeps the key out of the image.
 */

let client: SupabaseClient | null = null

function connect(): SupabaseClient {
  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || ''
  const key =
    process.env.SUPABASE_SERVICE_KEY ||
    process.env.SUPABASE_ANON_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    ''

  // Fail with the name of what is missing. `createClient` would otherwise throw
  // "supabaseUrl is required", which reads as a code fault rather than an
  // unset variable on the host.
  if (!url || !key) {
    const missing = [!url && 'SUPABASE_URL', !key && 'SUPABASE_SERVICE_KEY'].filter(Boolean)
    throw new Error(`Supabase is not configured: ${missing.join(' and ')} unset on this service.`)
  }

  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  })
}

export const supabaseAdmin: SupabaseClient = new Proxy({} as SupabaseClient, {
  get(_target, prop) {
    if (!client) {
      client = connect()
    }

    const value = Reflect.get(client, prop, client)
    // Methods are handed out detached from the client, so bind them back to it.
    return typeof value === 'function' ? value.bind(client) : value
  },
})
