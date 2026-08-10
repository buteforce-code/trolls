/**
 * Formatting shared by every view.
 *
 * All of it is locale-pinned to en-IN and IST-agnostic (the values arrive as
 * ISO strings and are rendered in the viewer's zone). The pipeline is operated
 * from India and every number on screen — rupees, impressions, word counts —
 * is read against Indian grouping, so `toLocaleString('en-IN')` is the default
 * rather than a per-call decision someone forgets to make.
 */

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

function toMs(value: string | number | Date): number {
  if (value instanceof Date) return value.getTime()
  if (typeof value === 'number') return value
  return new Date(value).getTime()
}

/** "just now" · "12m ago" · "3h ago" · "5d ago" */
export function relative(value: string | number | Date | null | undefined): string {
  if (!value) return '—'
  const ms = toMs(value)
  if (Number.isNaN(ms)) return '—'
  const diff = Date.now() - ms
  if (diff < MINUTE) return 'just now'
  if (diff < HOUR) return `${Math.floor(diff / MINUTE)}m ago`
  if (diff < DAY) return `${Math.floor(diff / HOUR)}h ago`
  return `${Math.floor(diff / DAY)}d ago`
}

/** "in 12m" · "in 3h" · "in 2d" · "now" */
export function untilShort(value: string | number | Date | null | undefined): string {
  if (!value) return '—'
  const ms = toMs(value)
  if (Number.isNaN(ms)) return '—'
  const diff = ms - Date.now()
  if (diff <= 0) return 'now'
  const minutes = Math.round(diff / MINUTE)
  if (minutes < 60) return `in ${minutes}m`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `in ${hours}h`
  return `in ${Math.round(hours / 24)}d`
}

/**
 * A live countdown: "02:14:31" inside a day, "2d 6h" beyond it.
 *
 * This is the veto window made literal. A scheduled post publishes itself, and
 * the difference between "tomorrow" and a running clock is the difference
 * between a note and a deadline.
 */
export function countdown(value: string | number | Date | null | undefined): string {
  if (!value) return '—'
  const ms = toMs(value)
  if (Number.isNaN(ms)) return '—'
  const diff = ms - Date.now()
  if (diff <= 0) return 'publishing'
  const seconds = Math.floor(diff / 1000)
  const hours = Math.floor(seconds / 3600)
  if (hours >= 24) return `${Math.floor(hours / 24)}d ${hours % 24}h`
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(hours)}:${pad(Math.floor((seconds % 3600) / 60))}:${pad(seconds % 60)}`
}

/** Clock time for log lines. */
export function clockTime(value: string | number | Date | null | undefined): string {
  if (!value) return '--:--'
  const d = new Date(toMs(value))
  if (Number.isNaN(d.getTime())) return '--:--'
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/** Short calendar label: "4 Aug". */
export function dayLabel(value: string | number | Date): string {
  const d = new Date(toMs(value))
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

export function num(value: number | null | undefined, fallback = '—'): string {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback
  return value.toLocaleString('en-IN')
}

export function money(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `$${Number(value).toFixed(digits)}`
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function seconds(ms: number | null | undefined): string {
  if (!ms) return ''
  return `${(ms / 1000).toFixed(1)}s`
}

/** Compact duration for run cards: "21m 24s". */
export function duration(ms: number | null | undefined): string {
  if (!ms) return '—'
  const total = Math.round(ms / 1000)
  if (total < 60) return `${total}s`
  const m = Math.floor(total / 60)
  if (m < 60) return `${m}m ${total % 60}s`
  return `${Math.floor(m / 60)}h ${m % 60}m`
}

export interface Delta { text: string; tone: string }

/**
 * A period-over-period change, rendered as a signed percentage.
 *
 * `null` means "no previous period to compare against" — shown as "new" rather
 * than a fake +100%, which is the single most common way a dashboard lies.
 */
export function delta(value: number | null | undefined, betterWhenUp = true): Delta {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return { text: 'new', tone: 'var(--ink-mute)' }
  }
  const up = value >= 0
  const good = betterWhenUp ? up : !up
  return {
    text: `${up ? '▲' : '▼'} ${Math.abs(Math.round(value))}%`,
    tone: good ? 'var(--teal-ink)' : 'var(--rose-ink)',
  }
}

/** Word count from MDX/markdown body, tolerant of null. */
export function wordCount(body: string | null | undefined): number {
  if (!body) return 0
  return body.trim().split(/\s+/).filter(Boolean).length
}
