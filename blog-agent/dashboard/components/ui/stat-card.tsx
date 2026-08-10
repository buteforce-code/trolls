'use client'

import Link from 'next/link'
import { useCountUp } from '../../lib/use-count-up'

interface StatCardProps {
  label: string
  value: number
  /** Short qualifier pill beside the number ("waiting on you", "running"). */
  delta?: string
  sub?: string
  tone?: 'neutral' | 'teal' | 'lav' | 'rose'
  icon?: React.ReactNode
  href?: string
  index?: number
}

const TONES = {
  neutral: { border: 'var(--line)',      iconBg: 'var(--chip)',      iconInk: 'var(--ink-2)',    chip: 'chip--grey' },
  teal:    { border: 'var(--line)',      iconBg: 'var(--teal-tint)', iconInk: 'var(--teal-ink)', chip: 'chip--teal' },
  lav:     { border: 'var(--line)',      iconBg: 'var(--lav-tint)',  iconInk: 'var(--lav-ink)',  chip: 'chip--lav'  },
  rose:    { border: 'var(--rose-edge)', iconBg: 'var(--rose-tint)', iconInk: 'var(--rose-ink)', chip: 'chip--rose' },
} as const

/**
 * A headline number that is also a filter.
 *
 * Every stat card on the board answers a question the operator can act on, so
 * each one navigates to the lane it counts. A number you cannot click is a
 * number you have to go and find again.
 */
export function StatCard({ label, value, delta, sub, tone = 'neutral', icon, href, index = 0 }: StatCardProps) {
  const shown = useCountUp(value)
  const t = TONES[tone]

  const body = (
    <>
      <div className="row gap-12" style={{ marginBottom: 18 }}>
        {icon && (
          <span className="stat-icon" style={{ background: t.iconBg, color: t.iconInk }} aria-hidden="true">
            {icon}
          </span>
        )}
        <span className="stat-label">{label}</span>
      </div>
      <div className="row gap-10" style={{ alignItems: 'flex-end' }}>
        <span className="stat-value">{shown}</span>
        {delta && <span className={`chip ${t.chip}`} style={{ marginBottom: 3 }}>{delta}</span>}
      </div>
      {sub && <div className="stat-sub">{sub}</div>}
    </>
  )

  const className = `card card--tight rise${href ? ' card--interactive spotlight' : ''}`
  const style = { borderColor: t.border, '--i': index } as React.CSSProperties

  if (!href) return <div className={className} style={style}>{body}</div>

  return (
    <Link href={href} className={className} style={style}>
      {body}
    </Link>
  )
}
