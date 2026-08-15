'use client'

import Link from 'next/link'
import { LANES, type StatusGroup } from '../../lib/status'

interface LaneBarProps {
  active: StatusGroup
  counts: Record<StatusGroup, number>
  /** Topics matching the current lane *and* the current search. */
  shown: number
  total: number
}

/**
 * The header of a filtered lane.
 *
 * A lane is a working view, not a report. Everything the overview carries —
 * stat cards, the cadence chart, the village — is identical on every lane, so
 * rendering it here pushed the actual cards below the fold and made clicking
 * "Needs review" look like it had done nothing. This is what replaces it: the
 * lane you are in, how many are in it, and one click to any sibling lane.
 *
 * The counts come from the same `countByLane` the sidebar reads, so a lane can
 * never disagree with the rail that linked to it.
 */
export function LaneBar({ active, counts, shown, total }: LaneBarProps) {
  const filtered = shown !== total

  return (
    <nav className="lane-bar rise" style={{ '--i': 0 } as React.CSSProperties} aria-label="Lanes">
      <span className="lane-bar-count">
        <span className="display tnum lane-bar-n">{shown}</span>
        <span className="t-sm muted">
          {filtered ? `of ${total} in this lane` : shown === 1 ? 'topic' : 'topics'}
        </span>
      </span>

      <span className="lane-bar-rule" aria-hidden="true" />

      <span className="row wrap gap-8">
        <Link href="/" className="lane-chip" data-active={false}>
          All
        </Link>
        {LANES.map(lane => {
          const isActive = lane.key === active
          return (
            <Link
              key={lane.key}
              href={`/?lane=${lane.key}`}
              className="lane-chip"
              data-active={isActive}
              aria-current={isActive ? 'page' : undefined}
            >
              <span className="dot" style={{ background: lane.tone }} aria-hidden="true" />
              {lane.label}
              <span className="lane-chip-n">{counts[lane.key]}</span>
            </Link>
          )
        })}
      </span>
    </nav>
  )
}
