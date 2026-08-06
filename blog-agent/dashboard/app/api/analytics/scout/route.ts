import { NextResponse } from 'next/server'
import { spawnPythonJob } from '../../../../lib/python'
import { bearerMatches } from '../../../../lib/auth'

export const dynamic = 'force-dynamic'

/**
 * Trend sweep trigger.
 *
 * Fired every few hours by GitHub Actions. Spawns `python run.py --scout`,
 * which pulls Hacker News, this site's rising Search Console queries and the
 * Google Trends daily feed, gates each signal against the brand vocabulary and
 * stores the survivors for the ideator.
 *
 * Separate from the analytics ingest because the cadences genuinely differ:
 * Search Console publishes once a day, but a newsjackable story has a window of
 * roughly seventy-two hours, and a daily sweep would routinely miss a third of
 * it.
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

  console.log('[scout] sweep triggered — spawning run.py --scout')
  const { pid } = spawnPythonJob(['--scout'], 'scout', 'trend-scout')

  return NextResponse.json({ started: true, pid, at: new Date().toISOString() })
}
