'use client'

import { useState } from 'react'
import type { AutopilotState } from '../../lib/types'
import { untilShort } from '../../lib/format'
import { useToast } from '../ui/toast'

interface Props {
  state: AutopilotState | null
  queuedCount: number
  onRan: () => void
}

/**
 * The autopilot strip: what the engine will do next, and the two things the
 * operator can make it do now.
 *
 * One deliberate omission. The design draws a Pause/Resume button, but
 * autopilot is switched by the `AUTOPILOT_ENABLED` environment variable, read
 * by the Python process at start-up — there is no runtime toggle behind it. A
 * button that appeared to pause the engine and did not would be worse than no
 * button, so the state is reported and the mechanism is named instead.
 */
export function AutopilotStrip({ state, queuedCount, onRan }: Props) {
  const { toast } = useToast()
  const [busy, setBusy] = useState<'tick' | 'produce-all' | null>(null)

  if (!state) return null

  const next = state.scheduled[0]

  async function run(action: 'tick' | 'produce-all') {
    setBusy(action)
    try {
      const res = await fetch('/api/operator/autopilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        toast(data.error || 'Could not start the job', 'error')
        return
      }
      toast(action === 'tick'
        ? 'Tick fired — the engine is working'
        : 'Catch-up started — every queued topic will be researched and written')
      onRan()
    } catch {
      toast('Could not reach the server', 'error')
    } finally {
      setBusy(null)
    }
  }

  return (
    <section
      className="card card--tight rise spotlight"
      style={{ borderColor: 'var(--lav-edge)', marginBottom: 20, '--i': 1 } as React.CSSProperties}
      aria-label="Autopilot"
    >
      <div className="row wrap gap-14" style={{ position: 'relative', zIndex: 1 }}>
        <span className="row gap-8" style={{ fontWeight: 600 }}>
          <span
            className={`dot dot--lg${state.enabled ? ' pulse' : ''}`}
            style={{ color: state.enabled ? 'var(--lav-deep)' : 'var(--grey-dot)' }}
            aria-hidden="true"
          />
          Autopilot {state.enabled ? 'on' : 'paused'}
        </span>

        <span className="t-base muted">1 post every {state.gapHours}h</span>
        <span aria-hidden="true" style={{ width: 1, height: 16, background: 'var(--line)' }} />
        <span className="t-base muted">
          {state.scheduled.length} scheduled · {queuedCount} queued
        </span>
        <span className="t-base" style={{ fontWeight: 600, color: 'var(--lav-ink)' }}>
          {next ? `next ${untilShort(next.scheduled_for)}` : 'nothing scheduled'}
        </span>

        <span className="row gap-10 push">
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => run('tick')}
            disabled={busy !== null}
          >
            {busy === 'tick' && <span className="spinner" />}
            Run a tick
          </button>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => run('produce-all')}
            disabled={busy !== null}
          >
            {busy === 'produce-all' && <span className="spinner" />}
            Catch up queue
          </button>
        </span>
      </div>

      <p className="t-sm muted" style={{ marginTop: 12, position: 'relative', zIndex: 1 }}>
        Scheduled posts publish themselves unless you veto first. The hourly cron writes one
        topic per tick.{' '}
        {state.enabled
          ? 'Switched off server-side with AUTOPILOT_ENABLED=false.'
          : 'Switched back on server-side with AUTOPILOT_ENABLED=true.'}
      </p>
    </section>
  )
}
