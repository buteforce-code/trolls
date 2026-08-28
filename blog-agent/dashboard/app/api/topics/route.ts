import { NextResponse } from 'next/server'
// Service key, not anon: RLS on `topics` now has no policies, so an anon read
// returns zero rows rather than an error — a silent empty dashboard.
import { supabaseAdmin as supabase } from '../../../lib/supabase'

export const dynamic = 'force-dynamic'

/**
 * The board reads every topic it counts.
 *
 * This used to be `.select('*').limit(100)` with no total and no signal. The
 * brief plans for 40–100 topics "growing indefinitely", and the row after the
 * hundredth would have gone missing silently: not just absent from the grid, but
 * absent from "Topics in play", from every sidebar badge, from every lane count
 * and from search — all of which are computed client-side from this array. A
 * dashboard that quietly under-reports its own workload is worse than one that
 * refuses to load.
 *
 * So: a much higher ceiling, an exact count from the same query, and `truncated`
 * so the UI can say what it is not showing rather than pretend it is everything.
 */
const MAX_TOPICS = 1000

export async function GET() {
  const { data, error, count } = await supabase
    .from('topics')
    .select('*', { count: 'exact' })
    .order('updated_at', { ascending: false })
    .limit(MAX_TOPICS)

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  const topics = data ?? []
  const total = count ?? topics.length

  return NextResponse.json({ topics, total, truncated: total > topics.length })
}
