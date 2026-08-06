import { NextResponse } from 'next/server'
import { spawnPythonJob } from '../../../../lib/python'
import { bearerMatches } from '../../../../lib/auth'

export const dynamic = 'force-dynamic'

/**
 * Analytics ingestion trigger.
 *
 * Fired daily by GitHub Actions. Authenticates with the same shared secret as
 * the autopilot tick, then spawns `python run.py --ingest-analytics` in the
 * background and returns immediately.
 *
 * Reuses AUTOPILOT_TICK_SECRET rather than minting a second secret: both
 * endpoints are the same trust level (a scheduled job on the same repo firing
 * an internal maintenance task), and a second secret is one more thing to
 * rotate for no additional isolation.
 *
 * `?days=N` overrides the trailing window — used once for the initial backfill,
 * then left alone. Bounded to Search Console's own 16-month retention so a
 * typo cannot spawn an unbounded pull.
 */
const MAX_BACKFILL_DAYS = 480

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

  const args = ['--ingest-analytics']

  const raw = new URL(request.url).searchParams.get('days')
  if (raw !== null) {
    const days = Number.parseInt(raw, 10)
    if (!Number.isFinite(days) || days < 1 || days > MAX_BACKFILL_DAYS) {
      return NextResponse.json(
        { error: `days must be an integer between 1 and ${MAX_BACKFILL_DAYS}` },
        { status: 400 },
      )
    }
    args.push('--days', String(days))
  }

  console.log(`[analytics] ingest triggered — spawning run.py ${args.join(' ')}`)
  const { pid } = spawnPythonJob(args, 'analytics', 'analytics-ingest')

  return NextResponse.json({ started: true, pid, at: new Date().toISOString() })
}
