import { NextResponse } from 'next/server'
import {
  GAP_HOURS_MAX, GAP_HOURS_MIN, VETO_HOURS_MAX, VETO_HOURS_MIN,
  readSettings, writeSettings, type SettingsPatch,
} from '../../../lib/settings'
import { rateLimit } from '../../../lib/ratelimit'

export const dynamic = 'force-dynamic'

/**
 * The autonomy switches: read them, and change them.
 *
 * Deliberately at `/api/settings` and not under `/api/autopilot/`. That prefix is
 * listed in `middleware.ts` as PUBLIC — it has to be, because the GitHub Actions
 * cron cannot hold a browser session — and every route beneath it authenticates
 * with a bearer secret instead. Landing this route there would have published a
 * POST that turns off human review to the open internet. Here, the middleware
 * requires a session before the handler runs.
 *
 * POST accepts a partial patch: send only what you are changing. Anything absent
 * is left alone, so two operators changing different switches cannot clobber each
 * other's field by round-tripping a whole object.
 */

const MAX_BODY_KEYS = 8

function badRequest(message: string) {
  return NextResponse.json({ error: message }, { status: 400 })
}

/** Strict: a boolean must be a boolean. `"false"` and `0` are rejected rather
 *  than coerced, because coercing the string "false" to `true` is exactly how a
 *  switch ends up meaning the opposite of what the operator clicked. */
function readBool(value: unknown, name: string): boolean | undefined | Error {
  if (value === undefined) return undefined
  if (typeof value !== 'boolean') return new Error(`${name} must be true or false`)
  return value
}

function readHours(
  value: unknown, name: string, min: number, max: number,
): number | undefined | Error {
  if (value === undefined) return undefined
  if (typeof value !== 'number' || !Number.isInteger(value)) {
    return new Error(`${name} must be a whole number of hours`)
  }
  if (value < min || value > max) {
    return new Error(`${name} must be between ${min} and ${max}`)
  }
  return value
}

export async function GET() {
  const settings = await readSettings()
  return NextResponse.json({ settings })
}

export async function POST(request: Request) {
  // A settings write is cheap, but a script hammering the human-review switch
  // would still churn the row and its audit trail. Generous for a person.
  const limit = rateLimit('settings:write', 10, 60)
  if (!limit.allowed) {
    return NextResponse.json(
      { error: `Too many changes. Try again in ${limit.retryAfterSeconds}s.` },
      { status: 429, headers: { 'Retry-After': String(limit.retryAfterSeconds) } },
    )
  }

  let body: unknown
  try {
    body = await request.json()
  } catch {
    return badRequest('invalid JSON body')
  }
  if (typeof body !== 'object' || body === null || Array.isArray(body)) {
    return badRequest('body must be a JSON object')
  }

  const raw = body as Record<string, unknown>
  if (Object.keys(raw).length > MAX_BODY_KEYS) return badRequest('too many fields')

  const parsed = {
    autopilotEnabled: readBool(raw.autopilotEnabled, 'autopilotEnabled'),
    humanInTheLoop: readBool(raw.humanInTheLoop, 'humanInTheLoop'),
    publishGapHours: readHours(raw.publishGapHours, 'publishGapHours', GAP_HOURS_MIN, GAP_HOURS_MAX),
    vetoWindowHours: readHours(raw.vetoWindowHours, 'vetoWindowHours', VETO_HOURS_MIN, VETO_HOURS_MAX),
  }

  for (const value of Object.values(parsed)) {
    if (value instanceof Error) return badRequest(value.message)
  }

  const patch = Object.fromEntries(
    Object.entries(parsed).filter(([, value]) => value !== undefined),
  ) as SettingsPatch

  if (Object.keys(patch).length === 0) return badRequest('nothing to change')

  // Turning human review off means finished posts publish themselves to the live
  // site with nobody reading them first. Say so in the server log, because that
  // is the one line worth having when someone asks later why a post went out.
  if (patch.humanInTheLoop === false) {
    console.warn('[settings] human review switched OFF — posts will publish unreviewed')
  }

  const { settings, ignoredDueToEnv, error } = await writeSettings(patch, 'dashboard')
  if (error) {
    return NextResponse.json({ error: `Could not save: ${error}`, settings }, { status: 503 })
  }

  return NextResponse.json({ saved: true, settings, ignoredDueToEnv })
}
