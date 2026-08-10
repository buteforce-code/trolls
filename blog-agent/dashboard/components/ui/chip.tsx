import type { ChipTone } from '../../lib/status'
import { statusMeta } from '../../lib/status'

interface ChipProps {
  tone?: ChipTone
  /** Renders a leading dot; `live` makes it pulse. */
  dot?: boolean
  live?: boolean
  large?: boolean
  className?: string
  children: React.ReactNode
}

export function Chip({ tone = 'grey', dot = false, live = false, large = false, className = '', children }: ChipProps) {
  return (
    <span className={`chip chip--${tone}${large ? ' chip--lg' : ''}${className ? ` ${className}` : ''}`}>
      {dot && <span className={`dot${live ? ' pulse pulse--fast' : ''}`} aria-hidden="true" />}
      {children}
    </span>
  )
}

/**
 * A topic's status, spelled the one agreed way.
 *
 * The pulsing dot appears only while an agent is genuinely executing. That is
 * the whole point of the tell — a dot that pulses on a queued topic would train
 * the operator to ignore it.
 */
export function StatusChip({ status, large = false }: { status: string; large?: boolean }) {
  const meta = statusMeta(status)
  return (
    <Chip tone={meta.tone} dot={meta.live} live={meta.live} large={large}>
      {meta.label}
    </Chip>
  )
}

/** A quiet tag pill — taxonomy, not state, so it never takes a semantic colour. */
export function Tag({ children }: { children: React.ReactNode }) {
  return <span className="chip chip--ghost">{children}</span>
}
