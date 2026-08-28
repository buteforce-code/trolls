/**
 * The pipeline's status vocabulary, and how each status is shown.
 *
 * One map, one place. Before this file the label for `verifying_draft` was
 * written out in four different components and had drifted into three different
 * strings; anything that renders a status now reads from here.
 *
 * The `group` is the more important half. An operator does not think in nine
 * statuses, they think in five lanes: what needs me, what is about to ship,
 * what is moving, what is waiting, what is done. The board, the sidebar counts
 * and the stat cards all group by that, never by raw status.
 */
import { untilShort } from './format'

export type StatusGroup = 'attention' | 'scheduled' | 'progress' | 'queued' | 'published'
export type ChipTone = 'lav' | 'teal' | 'rose' | 'grey' | 'amber'

export interface StatusMeta {
  label: string
  group: StatusGroup
  /** True while an agent is actually executing — drives the pulsing dot. */
  live: boolean
  tone: ChipTone
}

export const STATUS: Record<string, StatusMeta> = {
  queued:             { label: 'Queued',            group: 'queued',    live: false, tone: 'grey' },
  researching:        { label: 'Researching',       group: 'progress',  live: true,  tone: 'teal' },
  verifying_research: { label: 'Review · research', group: 'attention', live: false, tone: 'rose' },
  writing:            { label: 'Writing',           group: 'progress',  live: true,  tone: 'teal' },
  verifying_draft:    { label: 'Review · draft',    group: 'attention', live: false, tone: 'rose' },
  scheduled:          { label: 'Scheduled',         group: 'scheduled', live: false, tone: 'lav'  },
  publishing:         { label: 'Publishing',        group: 'progress',  live: true,  tone: 'teal' },
  published:          { label: 'Published',         group: 'published', live: false, tone: 'grey' },
  cancelled:          { label: 'Cancelled',         group: 'published', live: false, tone: 'grey' },
  failed:             { label: 'Needs a fix',       group: 'attention', live: false, tone: 'rose' },
}

const UNKNOWN: StatusMeta = { label: 'Unknown', group: 'queued', live: false, tone: 'grey' }

/** Never throws on a status the pipeline invents later. */
export function statusMeta(status: string | null | undefined): StatusMeta {
  return (status && STATUS[status]) || UNKNOWN
}

export interface LaneDef {
  key: StatusGroup
  label: string
  /** The dot colour beside the lane heading. */
  tone: string
}

export const LANES: LaneDef[] = [
  { key: 'attention', label: 'Needs your attention', tone: 'var(--rose)' },
  { key: 'scheduled', label: 'Scheduled',            tone: 'var(--lav-deep)' },
  { key: 'progress',  label: 'In progress',          tone: 'var(--teal)' },
  { key: 'queued',    label: 'Queued',               tone: 'var(--grey-dot)' },
  { key: 'published', label: 'Published',            tone: 'var(--grey-dot)' },
]

export const LANE_TITLE: Record<string, string> = {
  all:       'Pipeline',
  attention: 'Needs your attention',
  scheduled: 'Scheduled',
  progress:  'In progress',
  queued:    'Queued',
  published: 'Published',
}

/** Count topics per lane in one pass. */
export function countByLane<T extends { status: string }>(topics: readonly T[]): Record<StatusGroup, number> {
  const counts: Record<StatusGroup, number> = {
    attention: 0, scheduled: 0, progress: 0, queued: 0, published: 0,
  }
  for (const t of topics) counts[statusMeta(t.status).group] += 1
  return counts
}

/**
 * The six visible stages of the pipeline, and which one a status is sitting in.
 * Returns -1 for `queued` (nothing has started) and 6 for `published` (all done).
 */
export const STAGES = ['Research', 'Audit', 'Write', 'Verify', 'Schedule', 'Publish'] as const

const STAGE_INDEX: Record<string, number> = {
  queued: -1,
  researching: 0,
  verifying_research: 1,
  writing: 2,
  verifying_draft: 3,
  scheduled: 4,
  publishing: 5,
  published: 6,
  cancelled: 6,
}

export type StageState = 'pending' | 'active' | 'done' | 'failed'

/**
 * `failedAt` is where the run died. The pipeline does not currently persist a
 * stage index on failure, so callers pass what they can infer from the last
 * populated artefact; absent that it falls back to the write stage, which is
 * where the overwhelming majority of failures happen.
 */
export function stageStates(status: string, failedAt: number | null = null): StageState[] {
  const active = status === 'failed' ? (failedAt ?? 2) : (STAGE_INDEX[status] ?? -1)
  return STAGES.map((_, i) => {
    if (status === 'failed' && i === active) return 'failed'
    if (status === 'published' || status === 'cancelled') return 'done'
    if (i < active) return 'done'
    if (i === active) return 'active'
    return 'pending'
  })
}

/** One-line answer to "what is happening to this topic right now?" */
export function substatus(
  status: string,
  scheduledFor?: string | null,
  heldCount?: number | null,
  lastError?: string | null,
): string {
  switch (status) {
    case 'queued':             return 'Waiting its turn'
    case 'researching':        return 'The research agent is gathering sources'
    case 'verifying_research': return heldCount ? `Held ${heldCount} times · needs a human` : 'At the audit gate'
    case 'writing':            return 'Writer, humaniser and linker running'
    case 'verifying_draft':    return 'At the draft gate'
    case 'scheduled':          return scheduledFor ? `Auto-publishes ${untilShort(scheduledFor)}` : 'Scheduled'
    case 'publishing':         return 'Posting to the site API'
    case 'published':          return 'Live on the blog'
    case 'cancelled':          return 'Cancelled'
    case 'failed':             return classifyFailure(lastError).substatus
    default:                   return ''
  }
}

/* ── Why a run failed ────────────────────────────────────────────────────────
 *
 * `failed` used to render as "Needs a fix · A stage crashed" whatever had
 * happened. On 2026-08-27 eight topics failed together on a single OpenRouter
 * 402 — the account was out of credit — and the dashboard told the operator
 * eight times that a stage had crashed. Nothing had crashed. The only action
 * that would help was topping up an account, and the only way to learn that was
 * to open a SQL console and read `blog_posts.last_error` by hand.
 *
 * So the failure text is classified here, and the UI says which of two very
 * different things happened:
 *
 *   blocked — an external account condition. Retrying is futile until a human
 *             fixes something outside this system. The banner names it and
 *             links to the fix.
 *   crash   — the pipeline itself broke on this topic. Retry may well work.
 *
 * This mirrors `swarm/failures.py` on the Python side, which classifies the same
 * strings to decide whether to retry. Two implementations of one rule is a real
 * cost; the alternative was shipping the classification through the API as a new
 * column, which is a schema change for something the raw text already carries.
 * If the phrase tables drift apart, the Python one is the source of truth — it
 * is the one with tests written against the real stored errors.
 */
export type FailureKind = 'blocked' | 'crash'

export interface FailureMeta {
  kind: FailureKind
  /** The one-line substatus, e.g. under the title. */
  substatus: string
  /** The banner headline — what actually happened, in plain words. */
  headline: string
  /** What the operator should do next. Empty when we genuinely don't know. */
  action: string
  /** Where the fix lives, when it is somewhere outside this dashboard. */
  href: string | null
  /** The provider's own words, for the operator who wants them. */
  raw: string
}

const OPENROUTER_CREDITS_URL = 'https://openrouter.ai/settings/credits'

/**
 * Phrases that mean "an external account is blocking this", with the message and
 * the fix for each. Order matters: the first match wins, so the specific billing
 * phrases sit ahead of the looser auth ones.
 *
 * Kept narrow on purpose. A phrase that also appears in a transient error would
 * tell the operator to go fix their billing when the pipeline just needs a retry,
 * which is a worse lie than the one this replaces.
 */
interface Blocker {
  /** The `[kind]` tag swarm/failures.py stamps on the front of a blocked error. */
  tag: string
  /** Provider wording, for the errors stored before that tag existed. */
  match: readonly string[]
  headline: string
  action: string
  href: string | null
}

const BLOCKERS: readonly Blocker[] = [
  {
    tag: '[credits]',
    match: [
      'requires more credits', 'add more credits', 'openrouter_credits',
      'insufficient credits', 'insufficient_quota', 'exceeded your current quota',
      'credit balance is too low', 'payment required',
    ],
    headline: 'The LLM account is out of credit — nothing is broken in the pipeline.',
    action: 'Add credits to the provider account, then resume. Retrying before that fails identically.',
    href: OPENROUTER_CREDITS_URL,
  },
  {
    tag: '[auth]',
    match: [
      'invalid api key', 'incorrect api key', 'api key not valid',
      'no auth credentials', 'unauthorized',
    ],
    headline: 'The LLM provider rejected the API key.',
    action: 'Check the provider key in the environment — it may be missing, wrong, or revoked.',
    href: null,
  },
  {
    tag: '[invalid_request]',
    match: ['is not a valid model', 'model_not_found', 'maximum context length'],
    headline: 'The provider rejected the request itself.',
    action: 'Usually an unknown model name in the LLM_MODEL_* routing, or a prompt over the context window.',
    href: null,
  },
]

/** Never throws, and treats a missing or unrecognised error as an ordinary crash. */
export function classifyFailure(lastError?: string | null): FailureMeta {
  const raw = (lastError ?? '').trim()
  const haystack = raw.toLowerCase()

  // The tag is checked first and on its own: an error that came through the new
  // classifier already carries the verdict, so the UI does not have to re-derive
  // it from provider wording that may change.
  const blocker =
    BLOCKERS.find(b => haystack.includes(b.tag)) ??
    BLOCKERS.find(b => b.match.some(phrase => haystack.includes(phrase)))

  if (blocker) {
    return {
      kind: 'blocked',
      substatus: 'Blocked on the LLM account — not a code failure',
      headline: blocker.headline,
      action: blocker.action,
      href: blocker.href,
      raw,
    }
  }

  return {
    kind: 'crash',
    substatus: 'A stage crashed',
    headline: raw || 'A stage crashed and needs your action.',
    action: raw ? '' : 'Open the run to see which agent failed.',
    href: null,
    raw,
  }
}
