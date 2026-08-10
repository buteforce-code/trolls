'use client'

import { useState } from 'react'

export interface CalibrationBucket {
  range: string
  predicted: number
  actual: number
  n: number
}

const S = 200

/**
 * Does the engine's confidence match reality?
 *
 * Each dot is a confidence band: x is what the engine predicted, y is what
 * happened, dot size is how many posts are in the band. Dots on the dashed
 * diagonal mean calibrated. This is the check that decides whether the beliefs
 * on this page are worth acting on, which is why it is a chart and not a single
 * number — a good Brier score can hide an arm that is confidently wrong in one
 * band and compensating in another.
 */
export function CalibrationChart({ buckets, brier, n }: {
  buckets: readonly CalibrationBucket[]
  brier: number | null
  n: number
}) {
  const [active, setActive] = useState<number | null>(null)

  if (buckets.length === 0) {
    return (
      <p className="t-base muted" style={{ lineHeight: 1.65 }}>
        No calibration yet. It needs matured posts whose outcome is known, so it appears a couple
        of weeks after the first posts publish — not because the check is disabled, but because
        there is nothing yet to check against.
      </p>
    )
  }

  const reading = active !== null ? buckets[active] : null

  return (
    <div className="row wrap gap-22" style={{ alignItems: 'center' }}>
      <div style={{ position: 'relative', width: S, height: S, flex: 'none', background: 'var(--surface-sunk)', borderRadius: 12 }}>
        <svg
          viewBox={`0 0 ${S} ${S}`}
          style={{ position: 'absolute', inset: 0, width: S, height: S }}
          role="img"
          aria-label={`Calibration: ${buckets.map(b => `${b.range} predicted ${Math.round(b.predicted * 100)} percent, actual ${Math.round(b.actual * 100)} percent`).join('; ')}`}
        >
          <line x1="0" y1={S} x2={S} y2="0" stroke="var(--line-strong)" strokeDasharray="4 4" />
          {/*
            Each dot is focusable, not just hoverable. The qualitative reading
            below ("the engine is overconfident in this band") is the most useful
            sentence on the chart, and a mouse-only reveal puts it out of reach
            of keyboard and switch users entirely.
          */}
          {buckets.map((bucket, i) => (
            <circle
              key={bucket.range}
              className="svg-node"
              cx={bucket.predicted * S}
              cy={S - bucket.actual * S}
              r={active === i
                ? Math.max(4, Math.min(14, bucket.n * 2)) + 4
                : Math.max(4, Math.min(14, bucket.n * 2))}
              fill="var(--lav-deep)"
              opacity={active !== null && active !== i ? 0.22 : 0.6}
              tabIndex={0}
              role="button"
              aria-label={`${bucket.range} band: predicted ${Math.round(bucket.predicted * 100)} percent, actual ${Math.round(bucket.actual * 100)} percent, ${bucket.n} posts`}
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
            />
          ))}
        </svg>
      </div>

      <div style={{ flex: 1, minWidth: 200 }}>
        <p className="display" style={{ fontWeight: 700, fontSize: 28, letterSpacing: '-.03em' }}>
          {brier !== null ? brier.toFixed(3) : '—'}
        </p>
        <p className="t-base muted" style={{ margin: '4px 0 10px' }}>
          Brier score over {n} post{n === 1 ? '' : 's'}
        </p>

        {reading && (
          <div style={{ background: '#F6F4FD', borderRadius: 12, padding: '11px 13px', marginBottom: 11 }}>
            <p className="t-base" style={{ fontWeight: 600, color: 'var(--lav-ink)' }}>
              Predicted {Math.round(reading.predicted * 100)}% → actual {Math.round(reading.actual * 100)}%
            </p>
            <p className="t-sm" style={{ color: 'var(--ink-2)', marginTop: 5, lineHeight: 1.55 }}>
              The {reading.range} band, {reading.n} post{reading.n === 1 ? '' : 's'}.{' '}
              {Math.abs(reading.predicted - reading.actual) < 0.08
                ? 'Close to the line — well calibrated here.'
                : reading.actual > reading.predicted
                  ? 'Reality beat the forecast: the engine is underconfident in this band.'
                  : 'Reality fell short: the engine is overconfident in this band.'}
            </p>
          </div>
        )}

        <p className="t-sm" style={{ color: 'var(--ink-mute)', lineHeight: 1.6 }}>
          0 is a perfect forecast. 0.25 is what you get by always guessing 50%. Dots on the dashed
          line mean the engine&apos;s confidence matches reality — the bar it must clear before it
          may reorder the queue.
        </p>
      </div>
    </div>
  )
}
