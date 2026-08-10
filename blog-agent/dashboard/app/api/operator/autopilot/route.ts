import { NextResponse } from 'next/server'
import { spawnPythonJob } from '../../../../lib/python'
import { rateLimit } from '../../../../lib/ratelimit'

export const dynamic = 'force-dynamic'

/**
 * Operator-triggered autopilot actions.
 *
 * Why this exists alongside `/api/autopilot/tick`
 * -----------------------------------------------
 * The cron routes under `/api/autopilot/` are listed in `middleware.ts` as
 * PUBLIC_PREFIXES — they have to be, because GitHub Actions cannot hold a
 * browser session — and they authenticate with `AUTOPILOT_TICK_SECRET` instead.
 * That secret lives on the server and must never reach the browser, so the
 * dashboard genuinely cannot call them: a "Run a tick" button in the UI would
 * either not work or would require shipping the cron secret to every client.
 *
 * This route is the operator's door to the same two jobs. It sits OUTSIDE the
 * public prefixes, so `middleware.ts` requires a valid session before the
 * handler ever runs, and the cron secret stays server-side.
 *
 * Both actions spawn a long Python job, so they are rate-limited per instance.
 * A double-click on "Catch up queue" starting two `--produce-all` processes
 * against the same queue is a real way to burn the LLM budget twice.
 */

const ACTIONS = {
  tick: { args: ['--autopilot'], label: 'autopilot' },
  'produce-all': { args: ['--produce-all'], label: 'produce-all' },
} as const

type Action = keyof typeof ACTIONS

function isAction(value: unknown): value is Action {
  return value === 'tick' || value === 'produce-all'
}

export async function POST(request: Request) {
  let body: unknown
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: 'invalid JSON body' }, { status: 400 })
  }

  const action = (body as { action?: unknown } | null)?.action
  if (!isAction(action)) {
    return NextResponse.json(
      { error: "action must be 'tick' or 'produce-all'" },
      { status: 400 },
    )
  }

  // One tick a minute, one full catch-up every five. Both are generous for a
  // human pressing a button and tight enough to stop an accidental storm.
  const limit = action === 'tick'
    ? rateLimit('operator:tick', 1, 60)
    : rateLimit('operator:produce-all', 1, 300)
  if (!limit.allowed) {
    return NextResponse.json(
      { error: `Already running. Try again in ${limit.retryAfterSeconds}s.` },
      { status: 429, headers: { 'Retry-After': String(limit.retryAfterSeconds) } },
    )
  }

  // Fail loudly here rather than returning 200 and letting the spawned process
  // die silently in the background with no key.
  const provider = (process.env.LLM_PROVIDER || 'openai').toLowerCase()
  if (provider === 'openai' && !process.env.OPENAI_API_KEY) {
    return NextResponse.json(
      { error: 'OPENAI_API_KEY is not configured on the server' },
      { status: 503 },
    )
  }

  const { args, label } = ACTIONS[action]
  console.log(`[operator] ${action} triggered from the dashboard`)
  const { pid } = spawnPythonJob([...args], label, label)

  return NextResponse.json({ started: true, action, pid, at: new Date().toISOString() })
}
