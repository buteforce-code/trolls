'use client'

import { useMemo, useState } from 'react'
import { sampleBeta } from '../../lib/beta-sample'

export interface Arm {
  arm: string
  cluster: string | null
  source_platform: string | null
  alpha: number | string | null
  beta: number | string | null
  trials: number | string | null
  mean: number | string | null
  ci_low: number | string | null
  ci_high: number | string | null
  density: { x: number; y: number }[] | null
}

const COLOURS = [
  'var(--lav-deep)', 'var(--teal)', 'var(--lav-ink)',
  'var(--amber)', 'var(--rose)', '#7A6AA8',
]

const W = 760
const H = 230
const PAD = { left: 46, right: 14, top: 14, bottom: 38 }
const plotW = W - PAD.left - PAD.right
const plotH = H - PAD.top - PAD.bottom

const n = (value: number | string | null | undefined, fallback = 0): number => {
  const parsed = typeof value === 'string' ? Number(value) : value
  return typeof parsed === 'number' && Number.isFinite(parsed) ? parsed : fallback
}

const asPercent = (v: number) => `${Math.round(v * 100)}%`

/**
 * One curve per arm: the engine's belief about how often that content
 * cluster × source combination succeeds.
 *
 * The curves are the ones Python computed and stored in `bandit_arms.density`,
 * not a re-derivation here. If the dashboard drew its own Beta the chart and
 * the production queue could disagree, and the chart would be the more
 * convincing of the two.
 */
export function PosteriorChart({ arms }: { arms: readonly Arm[] }) {
  const [hovered, setHovered] = useState<number | null>(null)
  const [pinned, setPinned] = useState<number | null>(null)
  const [draws, setDraws] = useState<{ values: number[]; winner: number } | null>(null)

  const focus = pinned ?? hovered

  /**
   * The y-domain is the 90th percentile of density, not the maximum.
   *
   * An arm with almost no evidence has a Beta that spikes towards infinity at
   * the edge. Scaling every curve to that spike squashes the five informative
   * curves into a flat line along the axis — technically faithful, and useless.
   * Clipping the tail keeps the comparison between arms legible; the clipped
   * region is called out under the chart rather than hidden.
   */
  const { maxDensity, clipped } = useMemo(() => {
    const all = arms.flatMap(a => (a.density ?? []).map(p => p.y)).sort((a, b) => a - b)
    if (all.length === 0) return { maxDensity: 1, clipped: false }
    const p90 = all[Math.floor(all.length * 0.9)] || all[all.length - 1]
    const top = Math.max(0.001, p90 * 1.15)
    return { maxDensity: top, clipped: all[all.length - 1] > top * 1.02 }
  }, [arms])

  const x = (v: number) => PAD.left + v * plotW
  // Clamped so a clipped curve stops at the top edge instead of drawing off-canvas.
  const y = (v: number) => Math.max(PAD.top, PAD.top + plotH - (v / maxDensity) * plotH)

  const paths = useMemo(() => arms.map(arm => {
    const points = arm.density ?? []
    if (points.length === 0) return { line: '', area: '' }
    const line = points
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.x).toFixed(1)},${y(p.y).toFixed(1)}`)
      .join(' ')
    return { line, area: `${line} L${x(1)},${y(0)} L${x(0)},${y(0)} Z` }
  }), [arms, maxDensity]) // eslint-disable-line react-hooks/exhaustive-deps

  function draw() {
    const values = arms.map(a => sampleBeta(n(a.alpha, 1), n(a.beta, 1)))
    const winner = values.indexOf(Math.max(...values))
    setDraws({ values, winner })
  }

  if (arms.length === 0) return null

  const summary = arms
    .map(a => `${a.arm} believed ${asPercent(n(a.mean))}`)
    .join('; ')

  return (
    <>
      <div className="x-scroll">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          style={{ width: '100%', minWidth: 540, height: 'auto' }}
          role="img"
          aria-label={`Believed success rate per arm. ${summary}.`}
        >
          {[0, 0.25, 0.5, 0.75, 1].map(t => (
            <g key={t}>
              <line x1={x(t)} y1={PAD.top} x2={x(t)} y2={PAD.top + plotH} stroke="var(--chip)" strokeWidth="1" />
              <text x={x(t)} y={H - 16} fontSize="11" fill="var(--ink-faint)" textAnchor="middle">
                {asPercent(t)}
              </text>
            </g>
          ))}
          <text x={W / 2} y={H - 2} fontSize="10.5" fill="var(--ink-faint)" textAnchor="middle">
            believed success rate
          </text>

          {arms.map((arm, i) => {
            const dimmed = focus !== null && focus !== i
            const active = focus === i
            const colour = COLOURS[i % COLOURS.length]
            const mean = n(arm.mean)
            return (
              <g key={arm.arm}>
                <path
                  className="svg-curve"
                  d={paths[i].area}
                  fill={colour}
                  opacity={dimmed ? 0.02 : active ? 0.14 : 0.07}
                />
                <path
                  className="svg-curve"
                  d={paths[i].line}
                  fill="none"
                  stroke={colour}
                  strokeWidth={active ? 3.4 : 2.2}
                  opacity={dimmed ? 0.13 : 1}
                />
                <line
                  className="svg-curve"
                  x1={x(mean)} y1={PAD.top + plotH}
                  x2={x(mean)} y2={PAD.top + plotH - 9}
                  stroke={colour} strokeWidth="2.2"
                  opacity={dimmed ? 0.13 : 1}
                />
              </g>
            )
          })}

          {draws && arms.map((arm, i) => (
            <circle
              key={`draw-${arm.arm}`}
              className="svg-dot"
              cx={x(draws.values[i])}
              cy={PAD.top + plotH}
              r={draws.winner === i ? 7.5 : 5}
              fill={COLOURS[i % COLOURS.length]}
              stroke="#fff"
              strokeWidth="2"
            />
          ))}
        </svg>
      </div>

      <div className="row wrap gap-12" style={{ marginTop: 14 }}>
        <button type="button" className="btn btn--ghost btn--sm" onClick={draw}>
          {draws ? 'Draw again' : 'Draw from the posteriors'}
        </button>
        {draws && (
          <button type="button" className="btn btn--ghost btn--sm" onClick={() => setDraws(null)}>
            Clear
          </button>
        )}
        <p className="t-sm muted" style={{ flex: 1, minWidth: 240, lineHeight: 1.55 }} aria-live="polite">
          {draws
            ? `Drew ${draws.values.map(asPercent).join(' · ')} — ${arms[draws.winner].arm} wins this round.`
            : 'Each arm draws once from its own curve; the highest draw writes next. Wide curves win sometimes on luck alone — that is exploration, and it is the point.'}
        </p>
      </div>

      <ul className="chart-legend" style={{ marginTop: 14 }}>
        {arms.map((arm, i) => {
          const dimmed = focus !== null && focus !== i
          const colour = COLOURS[i % COLOURS.length]
          return (
            <li key={arm.arm}>
              <button
                type="button"
                className="legend-key"
                aria-pressed={pinned === i}
                data-pinned={pinned === i}
                data-off={dimmed}
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(i)}
                onBlur={() => setHovered(null)}
                onClick={() => setPinned(pinned === i ? null : i)}
              >
                <span className="legend-swatch" style={{ background: colour }} aria-hidden="true" />
                <span className="mono legend-label">{arm.arm}</span>
                <span className="legend-value" style={{ color: dimmed ? undefined : colour }}>
                  {asPercent(n(arm.mean))}
                </span>
                <span className="legend-meta t-xs">
                  {asPercent(n(arm.ci_low))}–{asPercent(n(arm.ci_high))} · n={n(arm.trials).toFixed(1)}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      <p className="t-xs" style={{ marginTop: 10, color: 'var(--ink-3)' }}>
        Hover an arm to isolate it · click to pin
        {clipped && ' · the vertical scale is clipped, so an arm with almost no evidence does not flatten the rest'}
      </p>
    </>
  )
}
