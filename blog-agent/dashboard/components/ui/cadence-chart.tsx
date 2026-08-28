import { dayLabel } from '../../lib/format'

export interface CadenceDay { date: string; count: number }

interface CadenceChartProps {
  days: readonly CadenceDay[]
  height?: number
}

/**
 * Thirty days of publishing, one bar a day.
 *
 * The encoding is deliberately coarse — silent, one, two-or-more — because the
 * question this chart answers is "is the engine keeping cadence?", not "how
 * many exactly". A silent day still draws a stub bar rather than nothing, so a
 * gap reads as a measured zero instead of missing data.
 */
export function CadenceChart({ days, height = 172 }: CadenceChartProps) {
  const max = Math.max(1, ...days.map(d => d.count))

  return (
    <>
      <ul
        className="row"
        style={{ alignItems: 'flex-end', gap: 6, height, listStyle: 'none' }}
        aria-label={`Posts published per day over the last ${days.length} days`}
      >
        {days.map((d, i) => {
          const label = `${dayLabel(d.date)} · ${d.count} ${d.count === 1 ? 'post' : 'posts'}`
          return (
            <li
              key={d.date}
              className="tip"
              data-tip={label}
              /* The outermost marks sit within half a tooltip of the card edge,
                 and the page clips its overflow — so "Today", the bar most often
                 pointed at, had its label cut in half. These two anchor to the
                 edge instead of centring on the bar. */
              data-tip-edge={i === 0 ? 'start' : i === days.length - 1 ? 'end' : undefined}
              style={{ flex: 1, display: 'flex', alignItems: 'flex-end', height: '100%', minWidth: 0 }}
            >
              <span className="sr-only">{label}</span>
              <span
                aria-hidden="true"
                className="bar-grow mark-hover"
                style={{
                  width: '100%',
                  maxWidth: 26,
                  margin: '0 auto',
                  height: d.count ? `${40 + (d.count / max) * 56}%` : 14,
                  borderRadius: 9,
                  /* A silent day drawn in --chip is 1.16:1 against the card —
                     the gap this chart exists to reveal was very nearly
                     invisible. --ink-faint clears 3:1 as a state indicator while
                     staying obviously quieter than either lavender, so a run of
                     silent days still reads as absence rather than as activity. */
                  background: d.count >= 2 ? 'var(--lav-deep)' : d.count === 1 ? 'var(--lav)' : 'var(--ink-faint)',
                  '--i': i,
                } as React.CSSProperties}
              />
            </li>
          )
        })}
      </ul>
      <div className="row t-sm faint" style={{ justifyContent: 'space-between', marginTop: 12 }}>
        <span>{days.length} days ago</span>
        <span>{Math.round(days.length / 2)} days</span>
        <span>Today</span>
      </div>

      {/*
        The per-bar tooltip is a CSS `:hover` affordance, which a keyboard-only
        user can never trigger. Rather than making thirty list items focusable
        and burying the rest of the page thirty tab stops deep, the same numbers
        are available here as one collapsed table.
      */}
      <details style={{ marginTop: 10 }}>
        <summary className="t-sm muted" style={{ cursor: 'pointer' }}>Show the days that published</summary>
        <div className="x-scroll" style={{ marginTop: 10 }}>
          <table className="table">
            <caption className="sr-only">Posts published per day</caption>
            <thead>
              <tr>
                <th scope="col">Day</th>
                <th scope="col" style={{ textAlign: 'right' }}>Posts</th>
              </tr>
            </thead>
            <tbody>
              {days.filter(d => d.count > 0).map(d => (
                <tr key={d.date}>
                  <td>{dayLabel(d.date)}</td>
                  <td className="tnum" style={{ textAlign: 'right' }}>{d.count}</td>
                </tr>
              ))}
              {days.every(d => d.count === 0) && (
                <tr><td colSpan={2}>Nothing published in this window.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </details>
    </>
  )
}

/** The three-swatch key that sits beside the chart heading. */
export function CadenceLegend() {
  const items = [
    { fill: 'var(--lav-deep)', label: 'Two posts' },
    { fill: 'var(--lav)', label: 'One post' },
    { fill: 'var(--chip)', label: 'Silent' },
  ]
  return (
    <div className="row wrap gap-14 t-sm muted">
      {items.map(i => (
        <span key={i.label} className="row gap-6">
          <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 3, background: i.fill }} />
          {i.label}
        </span>
      ))}
    </div>
  )
}
