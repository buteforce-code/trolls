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
export function substatus(status: string, scheduledFor?: string | null, heldCount?: number | null): string {
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
    case 'failed':             return 'A stage crashed'
    default:                   return ''
  }
}
