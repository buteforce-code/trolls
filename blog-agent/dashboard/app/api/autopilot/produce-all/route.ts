import { NextResponse } from 'next/server'
import { spawnPythonJob } from '../../../../lib/python'

export const dynamic = 'force-dynamic'

/**
 * One-shot catch-up trigger.
 *
 * Spawns `python run.py --produce-all`, which researches + audits + writes EVERY
 * queued topic now and schedules them on the publish cadence (24h apart). The
 * hourly autopilot tick then drips them out. Published posts are untouched.
 *
 * Same shared-secret auth as /api/autopilot/tick. Returns immediately — the work
 * runs in the background (it can take a while for a large queue).
 */
export async function POST(request: Request) {
  const secret = process.env.AUTOPILOT_TICK_SECRET || ''
  if (!secret) {
    return NextResponse.json(
      { error: 'AUTOPILOT_TICK_SECRET not configured on the server' },
      { status: 503 },
    )
  }

  const auth = request.headers.get('authorization') || ''
  const token = auth.replace(/^Bearer\s+/i, '').trim()
  if (token !== secret) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 })
  }

  console.log('[autopilot] produce-all triggered — spawning run.py --produce-all')
  const { pid } = spawnPythonJob(['--produce-all'], 'produce-all', 'produce-all')

  return NextResponse.json({ started: true, pid, at: new Date().toISOString() })
}
