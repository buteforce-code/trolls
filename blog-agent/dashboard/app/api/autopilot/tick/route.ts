import { NextResponse } from 'next/server'
import { spawnPythonJob } from '../../../../lib/python'

export const dynamic = 'force-dynamic'

/**
 * Autonomous tick trigger.
 *
 * Fired on a schedule by GitHub Actions (hourly). Authenticates with a shared
 * secret, then spawns `python run.py --autopilot` on the server. The Python
 * process does all the work (publish due posts, keep the buffer full, refill the
 * queue) in the background, so this returns immediately — the curl from the cron
 * job never blocks on minutes-long research/writing.
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

  console.log('[autopilot] tick triggered — spawning run.py --autopilot')
  const { pid } = spawnPythonJob(['--autopilot'], 'autopilot', 'autopilot')

  return NextResponse.json({ started: true, pid, at: new Date().toISOString() })
}
