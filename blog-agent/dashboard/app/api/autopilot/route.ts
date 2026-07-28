import { NextResponse } from 'next/server'
// Service key, not anon: RLS on `topics` now has no policies, so an anon read
// returns zero rows rather than an error — a silent empty dashboard.
import { supabaseAdmin as supabase } from '../../../lib/supabase'

export const dynamic = 'force-dynamic'

/**
 * Autopilot status for the dashboard header.
 * Reports the kill-switch state, cadence, and the list of posts currently
 * scheduled for auto-publish (the 24h veto window) so the operator can see
 * what's about to go live and pull anything back in time.
 */
export async function GET() {
  const enabled = (process.env.AUTOPILOT_ENABLED ?? 'true').toLowerCase() !== 'false'
  const gapHours = Number(process.env.PUBLISH_GAP_HOURS ?? '24')

  const { data, error } = await supabase
    .from('topics')
    .select('slug,title,scheduled_for')
    .eq('status', 'scheduled')
    .order('scheduled_for', { ascending: true })

  if (error) {
    return NextResponse.json({ enabled, gapHours, scheduled: [], error: error.message })
  }

  const scheduled = data || []
  const nextPublishAt = scheduled.length > 0 ? scheduled[0].scheduled_for : null

  return NextResponse.json({ enabled, gapHours, scheduled, nextPublishAt })
}
