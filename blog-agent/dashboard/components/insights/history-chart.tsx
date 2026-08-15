'use client'

import { useMemo, useState } from 'react'
import { dayLabel } from '../../lib/format'

export interface Snapshot {
  at: string
  posts_scored: number | string | null
  posts_matured: number | string | null
  arms: number | string | null
  global_rate: number | string | null
}

const W = 760
const H = 220
const PAD = { left: 40, right: 16, top: 16, bottom: 34 }
const plotW = W - PAD.left - PAD.right
const plotH = H - PAD.top - PAD.bottom

const n = (v: number | string | null | undefined, fallback = 0): number => {
  const parsed = typeof v === 'string' ? Number(v) : v
  return typeof parsed === 'number' && Number.isFinite(parsed) ? parsed : fallback
}

interface SeriesDef {
  key: 'posts_scored' | 'posts_matured' | 'arms'
  label: string
  colour: string
  hint: string
}

const SERIES: SeriesDef[] = [
  { key: 'posts_scored',  label: 'Posts scored',  colour: 'var(--lav-deep)', hint: 'every published post the scorer could read' },
  { key: 'posts_matured', label: 'Matured',       colour: 'var(--teal)',     hint: 'old enough to judge — this is the one that unlocks steering' },
  { key: 'arms',          label: 'Arms',          colour: 'var(--amber)',    hint: 'cluster × source combinations being tracked' },
]

/**
 * What the engine has learned, run over run.
 *
 * Every other chart on this page draws the newest snapshot only, which is why
 * the page looked frozen: a belief with no history cannot show itself changing.
 * `learning_snapshots` has been accumulating a row per `--learn` run all along
 * and the API already returned them — nothing rendered them.
 *
 * The maturity threshold is drawn as a reference line because it is the single
 * number that decides whether any of this is acted on. "12 of 25" is a status;
 * a line the series is visibly climbing towards is a forecast.
 */
export function HistoryChart({ snapshots, threshold }: {
  snapshots: readonly Snapshot[]
  threshold: number
}) {
  const [hidden, setHidden] = useState<Set<string>>(new Set())

  const visible = SERIES.filter(s => !hidden.has(s.key))

  const max = useMemo(() => {
    const values = snapshots.flatMap(s => visible.map(def => n(s[def.key])))
    return Math.max(1, threshold, ...values) * 1.12
  }, [snapshots, visible, threshold])

  if (snapshots.length < 2) {
    return (
      <p className="t-base muted" style={{ lineHeight: 1.65 }}>
        {snapshots.length === 0
          ? 'No learning runs recorded yet.'
          : 'Only one learning run so far. The trend appears from the second run — the engine '
            + 'scores nightly after the analytics ingest, so this fills in a day at a time.'}
      </p>
    )
  }

  const x = (i: number) => PAD.left + (i / Math.max(1, snapshots.length - 1)) * plotW
  const y = (v: number) => PAD.top + plotH - (v / max) * plotH

  const toggle = (key: string) => setHidden(prev => {
    const next = new Set(prev)
    // Never let the last series be hidden — an empty chart is not a view.
    if (next.has(key)) next.delete(key)
    else if (next.size < SERIES.length - 1) next.add(key)
    return next
  })

  const ticks = [0, 0.5, 1].map(t => Math.round(max * t))
  const first = snapshots[0]
  const last = snapshots[snapshots.length - 1]

  return (
    <>
      <div className="x-scroll">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          style={{ width: '100%', minWidth: 520, height: 'auto' }}
          role="img"
          aria-label={
            `Learning history over ${snapshots.length} runs. `
            + visible.map(s => `${s.label} went from ${n(first[s.key])} to ${n(last[s.key])}`).join('; ')
            + `. Maturity threshold ${threshold}.`
          }
        >
          {ticks.map(t => (
            <g key={t}>
              <line
                x1={PAD.left} y1={y(t)} x2={W - PAD.right} y2={y(t)}
                stroke="var(--line)" strokeWidth="1"
              />
              <text x={PAD.left - 8} y={y(t) + 4} fontSize="11" fill="var(--ink-3)" textAnchor="end">
                {t}
              </text>
            </g>
          ))}

          {/* The bar the engine has to clear before it may steer anything. */}
          {threshold <= max && (
            <g>
              <line
                x1={PAD.left} y1={y(threshold)} x2={W - PAD.right} y2={y(threshold)}
                stroke="var(--teal-ink)" strokeWidth="1.5" strokeDasharray="5 4" opacity=".75"
              />
              <text
                x={W - PAD.right} y={y(threshold) - 6}
                fontSize="10.5" fill="var(--teal-ink)" textAnchor="end" fontWeight="600"
              >
                steers at {threshold}
              </text>
            </g>
          )}

          {visible.map(def => {
            const path = snapshots
              .map((s, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(n(s[def.key])).toFixed(1)}`)
              .join(' ')
            return (
              <g key={def.key}>
                <path className="svg-curve" d={path} fill="none" stroke={def.colour} strokeWidth="2.4"
                      strokeLinejoin="round" strokeLinecap="round" />
                <circle
                  className="svg-dot"
                  cx={x(snapshots.length - 1)}
                  cy={y(n(last[def.key]))}
                  r="4"
                  fill={def.colour}
                />
              </g>
            )
          })}

          <text x={PAD.left} y={H - 10} fontSize="10.5" fill="var(--ink-3)">
            {dayLabel(first.at)}
          </text>
          <text x={W - PAD.right} y={H - 10} fontSize="10.5" fill="var(--ink-3)" textAnchor="end">
            {dayLabel(last.at)}
          </text>
        </svg>
      </div>

      <ul className="chart-legend" style={{ marginTop: 14 }}>
        {SERIES.map(def => {
          const off = hidden.has(def.key)
          return (
            <li key={def.key}>
              <button
                type="button"
                className="legend-key"
                data-off={off}
                aria-pressed={!off}
                onClick={() => toggle(def.key)}
                title={def.hint}
              >
                <span className="legend-swatch" style={{ background: def.colour }} aria-hidden="true" />
                <span className="legend-label">{def.label}</span>
                <span className="legend-value" style={{ color: off ? undefined : def.colour }}>
                  {n(last[def.key])}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </>
  )
}
