'use client'

import { useCallback, useMemo, useRef, useState } from 'react'
import { dayLabel, num, pct } from '../../lib/format'

export interface TrendPoint { date: string; impressions: number; clicks: number }

interface Props {
  series: readonly TrendPoint[]
}

const RANGES = [7, 14, 28] as const
const W = 720
const H = 180
const PAD_TOP = 12
const PAD_BOTTOM = 8

/**
 * Impressions and clicks, on two independent scales.
 *
 * Impressions outnumber clicks by roughly forty to one on this site. Plotted on
 * a shared axis the clicks line lies flat against the baseline and the only
 * chart that answers "is anyone actually arriving?" becomes unreadable. So each
 * series gets its own scale, and the chart says so out loud — an unlabelled
 * dual axis is a well-known way to imply a correlation that isn't there.
 *
 * Scrubbing works with a pointer and with arrow keys, and the same numbers the
 * tooltip shows are available to a screen reader as a table.
 */
export function SearchTrend({ series }: Props) {
  const [range, setRange] = useState<number>(28)
  const [showImpressions, setShowImpressions] = useState(true)
  const [showClicks, setShowClicks] = useState(true)
  const [focus, setFocus] = useState<number | null>(null)
  // Whether the current focus came from the keyboard. The live region only
  // speaks for keyboard scrubbing: a mouse sweeping the 28 bars would otherwise
  // fire 28 announcements at anyone running a screen reader alongside a mouse.
  const [announce, setAnnounce] = useState(false)
  const plotRef = useRef<HTMLDivElement>(null)

  const data = useMemo(() => series.slice(-range), [series, range])
  const maxImpressions = Math.max(1, ...data.map(d => d.impressions))
  const maxClicks = Math.max(1, ...data.map(d => d.clicks))

  const barWidth = W / Math.max(1, data.length)
  const plotHeight = H - PAD_TOP - PAD_BOTTOM

  const clickPath = useMemo(() => (
    data
      .map((d, i) => {
        const x = i * barWidth + barWidth / 2
        const y = PAD_TOP + plotHeight - (d.clicks / maxClicks) * plotHeight * 0.62
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  ), [data, barWidth, plotHeight, maxClicks])

  const onPointer = useCallback((event: React.MouseEvent) => {
    const rect = plotRef.current?.getBoundingClientRect()
    if (!rect || data.length === 0) return
    const i = Math.max(0, Math.min(data.length - 1, Math.floor(((event.clientX - rect.left) / rect.width) * data.length)))
    setAnnounce(false)
    setFocus(prev => (prev === i ? prev : i))
  }, [data.length])

  const onKeyDown = useCallback((event: React.KeyboardEvent) => {
    if (data.length === 0) return
    const current = focus ?? data.length - 1
    let next: number | null = null
    if (event.key === 'ArrowRight') next = Math.min(data.length - 1, current + 1)
    else if (event.key === 'ArrowLeft') next = Math.max(0, current - 1)
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = data.length - 1
    else if (event.key === 'Escape') { setFocus(null); return }
    if (next === null) return
    event.preventDefault()
    setAnnounce(true)
    setFocus(next)
  }, [focus, data.length])

  const active = focus !== null ? data[focus] : null

  return (
    <section className="card rise mb-22" style={{ '--i': 5 } as React.CSSProperties}>
      <div className="row wrap gap-18" style={{ alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h2 className="section-title">Search trend</h2>
          <p className="section-note">
            Daily impressions and clicks on two scales — impressions dwarf clicks by roughly 40×,
            and a shared axis would flatten the line that matters.
          </p>
        </div>
        <div className="row wrap gap-8">
          <button
            type="button"
            className="tab row gap-8"
            data-active={showImpressions}
            aria-pressed={showImpressions}
            onClick={() => setShowImpressions(v => !v)}
          >
            <span
              aria-hidden="true"
              style={{ width: 10, height: 10, borderRadius: 3, background: showImpressions ? 'var(--lav)' : '#E4E1EE' }}
            />
            impressions
          </button>
          <button
            type="button"
            className="tab row gap-8"
            data-active={showClicks}
            aria-pressed={showClicks}
            onClick={() => setShowClicks(v => !v)}
          >
            <span
              aria-hidden="true"
              style={{ width: 12, height: 3, borderRadius: 2, background: showClicks ? 'var(--teal)' : 'var(--line-strong)' }}
            />
            clicks
          </button>
          <span aria-hidden="true" style={{ width: 1, height: 18, background: 'var(--line)', margin: '0 3px' }} />
          {RANGES.map(r => (
            <button
              key={r}
              type="button"
              className="tab"
              data-active={range === r}
              aria-pressed={range === r}
              onClick={() => { setRange(r); setFocus(null) }}
            >
              {r}d
            </button>
          ))}
        </div>
      </div>

      <div
        ref={plotRef}
        tabIndex={0}
        role="group"
        aria-label="Search trend. Use the arrow keys to inspect each day."
        onMouseMove={onPointer}
        onMouseLeave={() => setFocus(null)}
        onKeyDown={onKeyDown}
        onFocus={() => { if (focus === null && data.length) { setAnnounce(true); setFocus(data.length - 1) } }}
        onBlur={() => { setFocus(null); setAnnounce(false) }}
        style={{ position: 'relative', cursor: 'crosshair', borderRadius: 'var(--r-md)' }}
      >
        <svg
          viewBox={`0 0 ${W} ${H}`}
          style={{ width: '100%', height: 'auto', display: 'block', overflow: 'visible' }}
          aria-hidden="true"
          focusable="false"
        >
          {showImpressions && data.map((d, i) => {
            const height = (d.impressions / maxImpressions) * plotHeight
            const dim = focus !== null && focus !== i
            return (
              <rect
                key={d.date}
                x={i * barWidth + barWidth * 0.14}
                y={PAD_TOP + plotHeight - height}
                width={barWidth * 0.72}
                height={Math.max(1, height)}
                rx={Math.min(5, barWidth * 0.3)}
                fill={focus === i ? 'var(--lav-deep)' : 'var(--lav)'}
                opacity={dim ? 0.5 : 1}
                style={{ transition: 'fill .18s ease, opacity .18s ease' }}
              />
            )
          })}

          {showClicks && data.length > 1 && (
            <path
              d={clickPath}
              fill="none"
              stroke="var(--teal)"
              strokeWidth="2.2"
              strokeLinejoin="round"
              strokeLinecap="round"
              opacity={focus !== null ? 0.85 : 1}
            />
          )}

          {focus !== null && (
            <line
              x1={focus * barWidth + barWidth / 2}
              x2={focus * barWidth + barWidth / 2}
              y1={0}
              y2={H}
              stroke="var(--lav)"
              strokeWidth="1"
            />
          )}

          {showClicks && active && (
            <circle
              cx={focus! * barWidth + barWidth / 2}
              cy={PAD_TOP + plotHeight - (active.clicks / maxClicks) * plotHeight * 0.62}
              r="5.5"
              fill="var(--teal)"
              stroke="#fff"
              strokeWidth="2.5"
            />
          )}
        </svg>

        {active && (
          <div
            style={{
              position: 'absolute',
              top: -8,
              left: `${((focus! + 0.5) / data.length) * 100}%`,
              transform: `translate(${focus! < 2 ? '0' : focus! > data.length - 3 ? '-100%' : '-50%'}, -100%)`,
              background: 'var(--ink)',
              borderRadius: 13,
              padding: '11px 14px',
              boxShadow: '0 16px 34px rgba(30,20,60,.26)',
              whiteSpace: 'nowrap',
              pointerEvents: 'none',
              zIndex: 30,
            }}
          >
            <div
              className="t-xs"
              style={{ color: '#A9A2C8', letterSpacing: '.07em', textTransform: 'uppercase', fontWeight: 700 }}
            >
              {dayLabel(active.date)}
            </div>
            <div className="row gap-14 tnum t-sm" style={{ marginTop: 7, color: '#F3F0FF' }}>
              <span className="row gap-6">
                <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--lav)' }} />
                {num(active.impressions)} impr
              </span>
              <span className="row gap-6">
                <span aria-hidden="true" style={{ width: 9, height: 3, borderRadius: 2, background: 'var(--teal)' }} />
                {active.clicks} clicks
              </span>
              <span style={{ color: '#A9A2C8' }}>
                CTR {active.impressions ? pct(active.clicks / active.impressions) : '—'}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Announced as the keyboard focus moves, so arrow-key scrubbing is not a
          silent interaction. Mouse movement deliberately stays quiet. */}
      <p aria-live="polite" className="sr-only">
        {announce && active
          ? `${dayLabel(active.date)}: ${active.impressions} impressions, ${active.clicks} clicks.`
          : ''}
      </p>

      <p className="t-xs faint" style={{ marginTop: 12 }}>
        Scrub the chart · impressions peak {num(maxImpressions)}/day, clicks {num(maxClicks)}/day
      </p>

      <details style={{ marginTop: 10 }}>
        <summary className="t-sm muted" style={{ cursor: 'pointer' }}>Show the numbers as a table</summary>
        <div className="x-scroll" style={{ marginTop: 10 }}>
          <table className="table">
            <caption className="sr-only">Daily search impressions and clicks</caption>
            <thead>
              <tr>
                <th scope="col">Day</th>
                <th scope="col" style={{ textAlign: 'right' }}>Impressions</th>
                <th scope="col" style={{ textAlign: 'right' }}>Clicks</th>
                <th scope="col" style={{ textAlign: 'right' }}>CTR</th>
              </tr>
            </thead>
            <tbody>
              {data.map(d => (
                <tr key={d.date}>
                  <td>{dayLabel(d.date)}</td>
                  <td className="tnum" style={{ textAlign: 'right' }}>{num(d.impressions)}</td>
                  <td className="tnum" style={{ textAlign: 'right' }}>{d.clicks}</td>
                  <td className="tnum" style={{ textAlign: 'right' }}>
                    {d.impressions ? pct(d.clicks / d.impressions) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  )
}
