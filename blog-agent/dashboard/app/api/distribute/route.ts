import { NextResponse } from 'next/server'
import { spawnPythonJob } from '../../../lib/python'
import { bearerMatches } from '../../../lib/auth'

export const dynamic = 'force-dynamic'

/**
 * Distribution tick.
 *
 * Spawns `python run.py --distribute`, which schedules the social kit of every
 * published post and sends at most one thing.
 *
 * The kits were already being written. `social.py` has produced a full LinkedIn
 * and X kit on every post since it was added — 33 of them by 2026-09-03 — and
 * not one had ever been posted anywhere. This route is the missing half.
 *
 * Runs twice a day rather than hourly, and sends at most one item per tick even
 * then. The queue holds a real backlog (165 sends across 33 posts on the first
 * run), and draining it at cron speed would empty three months of content into
 * an afternoon — bad for reach and unmistakably automated. `DISTRIBUTE_GAP_HOURS`
 * is the floor that actually enforces the spacing; the cron only offers chances
 * to send, it does not decide.
 *
 * Nothing goes out until `DISTRIBUTE_DRY_RUN=false`. That default is deliberate:
 * a blog post can be deleted quietly, a bad post on a real person's professional
 * profile is seen before it can be.
 *
 * Same bearer secret as the other scheduled jobs — see the ingest route for why
 * a second secret would add rotation work without adding isolation.
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

  console.log('[distribute] tick triggered — spawning run.py --distribute')
  const { pid } = spawnPythonJob(['--distribute'], 'distribute', 'distribute-tick')

  return NextResponse.json({ started: true, pid, at: new Date().toISOString() })
}
