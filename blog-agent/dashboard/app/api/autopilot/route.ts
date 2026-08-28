import { NextResponse } from 'next/server'
// Service key, not anon: RLS on `topics` now has no policies, so an anon read
// returns zero rows rather than an error — a silent empty dashboard.
import { supabaseAdmin as supabase } from '../../../lib/supabase'
import { readSettings } from '../../../lib/settings'

export const dynamic = 'force-dynamic'

/**
 * Autopilot status for the dashboard header.
 * Reports the two autonomy switches, the cadence, and the list of posts currently
 * scheduled for auto-publish (the veto window) so the operator can see what's
 * about to go live and pull anything back in time.
 *
 * The switches ride along on this response rather than on a request of their own.
 * The shell already polls this route every 3–10s, so the strip's control is
 * reconciled with the server on the same beat as everything else on the page —
 * one clock instead of two racing each other. Note this route is `/api/autopilot`
 * with no trailing slash: `middleware.ts` exempts the prefix `/api/autopilot/`,
 * so the cron routes below it are public and this one still requires a session.
 */
export async function GET() {
  const settings = await readSettings()

  // The engine's actual heartbeat.
  //
  // The sidebar used to infer liveness from `counts.progress > 0`, which is a
  // statement about topics, not about the worker: this engine writes one post an
  // hour at most, so zero-in-progress is its normal state for most of the day and
  // a worker that died weeks ago rendered identically to a healthy one. That is
  // precisely the failure DESIGN_BRIEF.md §6.1 warns about — "a control plane
  // whose own heartbeat is invisible is how you end up not noticing it died 41
  // days ago". `job_runs` records every background job the cron spawns, so the
  // last row in it is the last time anything actually ran.
  const [{ data, error }, lastJob] = await Promise.all([
    supabase
      .from('topics')
      .select('slug,title,scheduled_for')
      .eq('status', 'scheduled')
      .order('scheduled_for', { ascending: true }),
    supabase
      .from('job_runs')
      .select('job,started_at,ok')
      .order('started_at', { ascending: false })
      .limit(1)
      .maybeSingle(),
  ])

  const lastRun = lastJob.data
    ? { job: lastJob.data.job as string, at: lastJob.data.started_at as string, ok: lastJob.data.ok as boolean }
    : null

  // `enabled` and `gapHours` are kept at the top level: they are what the strip
  // has always read, and they now report the resolved setting rather than an
  // environment variable this process could see but never change.
  const base = {
    enabled: settings.autopilotEnabled,
    gapHours: settings.publishGapHours,
    settings,
    lastRun,
  }

  if (error) {
    return NextResponse.json({ ...base, scheduled: [], error: error.message })
  }

  const scheduled = data || []
  const nextPublishAt = scheduled.length > 0 ? scheduled[0].scheduled_for : null

  return NextResponse.json({ ...base, scheduled, nextPublishAt })
}
