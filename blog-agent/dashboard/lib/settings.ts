/**
 * The autonomy switches, read and written from the Node side.
 *
 * This is the TypeScript half of `swarm/settings.py`; the two read the same row
 * and must agree on precedence, or the dashboard would show a state the engine
 * does not act on. Keep them in step — the Python module carries the long-form
 * reasoning for why the switches live in Postgres at all (short version: the
 * worker is a new process on every tick, so an environment variable can be read
 * from the dashboard's process but never *thrown* from it).
 *
 * Precedence, identical on both sides: a set environment variable wins, then the
 * stored row, then the built-in default. Env is the break-glass — whoever holds
 * the host can force the engine off, or force the human back on, and no browser
 * session can override it. `sources` reports which one answered so the UI can say
 * "the host is overriding this" rather than render a switch that does nothing.
 */
import { supabaseAdmin as supabase } from './supabase'

export const SETTINGS_TABLE = 'autopilot_settings'
export const SETTINGS_ROW_ID = 1

/** Mirrors the CHECK constraints in setup_db.py. */
export const GAP_HOURS_MIN = 1
export const GAP_HOURS_MAX = 720
export const VETO_HOURS_MIN = 0
export const VETO_HOURS_MAX = 720

export type SettingKey =
  | 'autopilot_enabled'
  | 'human_in_the_loop'
  | 'publish_gap_hours'
  | 'veto_window_hours'

/** Which authority answered. 'fallback' means the read failed and we chose safety. */
export type SettingSource = 'env' | 'db' | 'default' | 'fallback'

export interface AutonomySettings {
  autopilotEnabled: boolean
  humanInTheLoop: boolean
  /** Cadence: minimum spacing between two published posts. */
  publishGapHours: number
  /** The human's reprieve before a finished post may publish. */
  vetoWindowHours: number
  sources: Record<SettingKey, SettingSource>
  /**
   * What the row itself holds, before any environment override. Null when the
   * read failed. The strip needs this to say "saved here as X, but the host is
   * forcing Y" — without it, an overridden switch could only report the value in
   * force, and the operator's own saved setting would vanish from the interface
   * that claims to show it.
   */
  stored: Partial<Record<SettingKey, boolean | number>> | null
  /** Set only when the row could not be read, so the UI can say so. */
  error?: string
}

const ENV_KEYS: Record<SettingKey, string> = {
  autopilot_enabled: 'AUTOPILOT_ENABLED',
  human_in_the_loop: 'HUMAN_IN_THE_LOOP',
  publish_gap_hours: 'PUBLISH_GAP_HOURS',
  veto_window_hours: 'VETO_WINDOW_HOURS',
}

const DEFAULTS: Record<SettingKey, boolean | number> = {
  autopilot_enabled: true,
  // False to match what the engine already does: autopilot has auto-advanced both
  // gates since it was written, so defaulting to true would halt a working
  // pipeline the moment this shipped. The *failure* fallback below is the
  // opposite, deliberately.
  human_in_the_loop: false,
  publish_gap_hours: 24,
  veto_window_hours: 24,
}

const TRUE_WORDS = new Set(['true', '1', 'yes', 'on'])
const FALSE_WORDS = new Set(['false', '0', 'no', 'off'])

/**
 * True/false when the variable is set to something recognisable, else null.
 * `null` means unset, which is not the same as false — the whole precedence rule
 * turns on that distinction. An unparseable value is null rather than a guess.
 */
function envBool(name: string): boolean | null {
  const raw = process.env[name]
  if (raw === undefined) return null
  const value = raw.trim().toLowerCase()
  if (TRUE_WORDS.has(value)) return true
  if (FALSE_WORDS.has(value)) return false
  return null
}

function envInt(name: string): number | null {
  const raw = process.env[name]
  if (raw === undefined) return null
  const value = Number.parseInt(raw.trim(), 10)
  return Number.isFinite(value) ? value : null
}

function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value))
}

/** Settings the host is currently overriding. The UI locks these controls. */
export function envOverrides(): Partial<Record<SettingKey, boolean | number>> {
  const out: Partial<Record<SettingKey, boolean | number>> = {}
  for (const key of Object.keys(ENV_KEYS) as SettingKey[]) {
    const value = typeof DEFAULTS[key] === 'boolean'
      ? envBool(ENV_KEYS[key])
      : envInt(ENV_KEYS[key])
    if (value !== null) out[key] = value
  }
  return out
}

function resolve(row: Record<string, unknown> | null, error?: string): AutonomySettings {
  const values: Record<SettingKey, boolean | number> = { ...DEFAULTS }
  const sources = {} as Record<SettingKey, SettingSource>

  for (const key of Object.keys(ENV_KEYS) as SettingKey[]) {
    const isBool = typeof DEFAULTS[key] === 'boolean'
    const fromEnv = isBool ? envBool(ENV_KEYS[key]) : envInt(ENV_KEYS[key])

    if (fromEnv !== null) {
      values[key] = fromEnv
      sources[key] = 'env'
    } else if (row && row[key] !== null && row[key] !== undefined) {
      values[key] = row[key] as boolean | number
      sources[key] = 'db'
    } else {
      sources[key] = 'default'
    }
  }

  // Failure is not permission. If we could not learn what the operator wants, we
  // report the human as in the loop — not knowing is a reason to stop at the gate,
  // never a reason to say "unattended publishing is on". Only where env did not
  // already speak: a host-level override is a deliberate instruction, not an unknown.
  if (error && sources.human_in_the_loop !== 'env') {
    values.human_in_the_loop = true
    sources.human_in_the_loop = 'fallback'
  }

  let stored: Partial<Record<SettingKey, boolean | number>> | null = null
  if (row) {
    stored = {}
    for (const key of Object.keys(ENV_KEYS) as SettingKey[]) {
      if (row[key] !== null && row[key] !== undefined) stored[key] = row[key] as boolean | number
    }
  }

  return {
    autopilotEnabled: Boolean(values.autopilot_enabled),
    humanInTheLoop: Boolean(values.human_in_the_loop),
    publishGapHours: clamp(Number(values.publish_gap_hours), GAP_HOURS_MIN, GAP_HOURS_MAX),
    vetoWindowHours: clamp(Number(values.veto_window_hours), VETO_HOURS_MIN, VETO_HOURS_MAX),
    sources,
    stored,
    error,
  }
}

/** Never throws: the strip must still render when the settings row is unreachable. */
export async function readSettings(): Promise<AutonomySettings> {
  try {
    const { data, error } = await supabase
      .from(SETTINGS_TABLE)
      .select('*')
      .eq('id', SETTINGS_ROW_ID)
      .maybeSingle()

    if (error) return resolve(null, error.message)
    // The table exists but has no row — treated as a failure, not as "all
    // defaults", because a half-run migration and a deliberate configuration
    // look identical from here and only one of them is consent.
    if (!data) return resolve(null, `no row with id=${SETTINGS_ROW_ID} in ${SETTINGS_TABLE}`)
    return resolve(data as Record<string, unknown>)
  } catch (err: unknown) {
    return resolve(null, err instanceof Error ? err.message : 'settings read failed')
  }
}

export interface SettingsPatch {
  autopilotEnabled?: boolean
  humanInTheLoop?: boolean
  publishGapHours?: number
  vetoWindowHours?: number
}

export interface WriteResult {
  settings: AutonomySettings
  /** Keys the caller asked to change that the host is overriding — the write
   *  landed in the row, but the engine will keep obeying the environment. */
  ignoredDueToEnv: SettingKey[]
  error?: string
}

/**
 * Persist a patch and return the resolved state.
 *
 * The write always lands in the row even when an environment override is in
 * force: the operator's intent is worth keeping, so that removing the override
 * later restores what they chose rather than a stale default. What it does NOT
 * do is pretend the change took effect — the caller gets `ignoredDueToEnv` and
 * the UI says so out loud.
 */
export async function writeSettings(
  patch: SettingsPatch,
  updatedBy: string,
): Promise<WriteResult> {
  const row: Record<string, unknown> = { id: SETTINGS_ROW_ID, updated_at: new Date().toISOString(), updated_by: updatedBy }
  const touched: SettingKey[] = []

  if (patch.autopilotEnabled !== undefined) {
    row.autopilot_enabled = patch.autopilotEnabled
    touched.push('autopilot_enabled')
  }
  if (patch.humanInTheLoop !== undefined) {
    row.human_in_the_loop = patch.humanInTheLoop
    touched.push('human_in_the_loop')
  }
  if (patch.publishGapHours !== undefined) {
    row.publish_gap_hours = clamp(patch.publishGapHours, GAP_HOURS_MIN, GAP_HOURS_MAX)
    touched.push('publish_gap_hours')
  }
  if (patch.vetoWindowHours !== undefined) {
    row.veto_window_hours = clamp(patch.vetoWindowHours, VETO_HOURS_MIN, VETO_HOURS_MAX)
    touched.push('veto_window_hours')
  }

  try {
    const { error } = await supabase.from(SETTINGS_TABLE).upsert(row, { onConflict: 'id' })
    if (error) return { settings: await readSettings(), ignoredDueToEnv: [], error: error.message }
  } catch (err: unknown) {
    return {
      settings: await readSettings(),
      ignoredDueToEnv: [],
      error: err instanceof Error ? err.message : 'settings write failed',
    }
  }

  const overrides = envOverrides()
  return {
    settings: await readSettings(),
    ignoredDueToEnv: touched.filter(key => overrides[key] !== undefined),
  }
}
