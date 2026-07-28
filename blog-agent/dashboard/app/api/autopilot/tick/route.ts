import { NextResponse } from 'next/server'
import { spawnPythonJob } from '../../../../lib/python'
import { bearerMatches } from '../../../../lib/auth'

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

  if (!bearerMatches(request.headers.get('authorization'), secret)) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 })
  }

  // Fail loudly at the trigger if the LLM key is missing, instead of returning 200
  // and letting the spawned Python job die silently in the background.
  const provider = (process.env.LLM_PROVIDER || 'openai').toLowerCase()
  if (provider === 'openai' && !process.env.OPENAI_API_KEY) {
    return NextResponse.json(
      { error: 'OPENAI_API_KEY not configured on the server — set it in the Render env' },
      { status: 503 },
    )
  }

  console.log('[autopilot] tick triggered — spawning run.py --autopilot')
  const { pid } = spawnPythonJob(['--autopilot'], 'autopilot', 'autopilot')

  return NextResponse.json({ started: true, pid, at: new Date().toISOString() })
}
