'use client'

import { useCallback, useEffect, useState } from 'react'
import type { AutopilotState } from '../../lib/types'
import type { SettingKey } from '../../lib/settings'
import { relative, untilShort } from '../../lib/format'
import { Dialog } from '../ui/dialog'
import { useToast } from '../ui/toast'

interface Props {
  state: AutopilotState | null
  queuedCount: number
  onRan: () => void
}

/** Setting key → the environment variable that overrides it, for naming the
 *  override in the interface. Mirrors ENV_KEYS in lib/settings.ts. */
const ENV_NAMES: [SettingKey, string][] = [
  ['autopilot_enabled', 'AUTOPILOT_ENABLED'],
  ['human_in_the_loop', 'HUMAN_IN_THE_LOOP'],
  ['publish_gap_hours', 'PUBLISH_GAP_HOURS'],
  ['veto_window_hours', 'VETO_WINDOW_HOURS'],
]

/**
 * The autopilot strip: what the engine will do next, the switch that decides
 * whether a person sees the work before the internet does, and the two things
 * the operator can make the engine do now.
 *
 * This component used to carry a note explaining that the Pause button in the
 * design could not be built, because autopilot was switched by an environment
 * variable read at process start and no browser could reach it. The switch is
 * real now — it is a row in Postgres that both the dashboard and the per-tick
 * Python worker read — so the note is gone and the control is here.
 *
 * Two things it must never do:
 *
 *   Lie about its own authority. An environment variable still wins over the
 *   stored setting, as the break-glass for whoever holds the host. When one is
 *   in force the switch is locked and says which value is being ignored, rather
 *   than moving and changing nothing — the exact failure the old note avoided by
 *   drawing no button at all.
 *
 *   Fight the poll. The shell re-fetches this state every 3–10s. A naive
 *   optimistic toggle flips, gets overwritten by an in-flight poll from before
 *   the write, and flips back. So a pending value shadows the server's until the
 *   server agrees with it, and then stops shadowing. The switch moves once.
 */
export function AutopilotStrip({ state, queuedCount, onRan }: Props) {
  const { toast } = useToast()
  const [busy, setBusy] = useState<'tick' | 'produce-all' | null>(null)
  const [saving, setSaving] = useState(false)
  const [confirmOff, setConfirmOff] = useState(false)

  // What we asked the server for, held until the server reports the same thing.
  // Null means "no local opinion — render exactly what the poll says".
  const [pendingReview, setPendingReview] = useState<boolean | null>(null)

  const settings = state?.settings
  // Absent settings means a response from before this shipped, or a failed read.
  // Either way the safe reading is that a human is still in the loop; claiming
  // unattended publishing on missing data is the one wrong answer here.
  const serverReview = settings?.humanInTheLoop ?? true

  useEffect(() => {
    if (pendingReview !== null && serverReview === pendingReview) setPendingReview(null)
  }, [serverReview, pendingReview])

  const reviewOn = pendingReview ?? serverReview
  const lockedByHost = settings?.sources?.human_in_the_loop === 'env'
  const storedReview = settings?.stored?.human_in_the_loop

  // Every setting the host is pinning, named. Two of these (AUTOPILOT_ENABLED,
  // PUBLISH_GAP_HOURS) predate this switch and are set in production today, so
  // the strip would otherwise report their values with no hint that the numbers
  // beside them are not the ones stored here.
  const pinned = ENV_NAMES.filter(([key]) => settings?.sources?.[key] === 'env').map(([, name]) => name)

  const save = useCallback(async (humanInTheLoop: boolean) => {
    setSaving(true)
    setPendingReview(humanInTheLoop)
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ humanInTheLoop }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setPendingReview(null)
        toast(data.error || 'Could not save the switch', 'error')
        return
      }
      // Adopt whatever the server resolved, not what we asked for. If an
      // environment override swallowed the change, this is where the switch
      // snaps back to the truth instead of sitting on a value nothing obeys.
      const resolved: boolean = data.settings?.humanInTheLoop ?? humanInTheLoop
      setPendingReview(resolved)
      if (data.ignoredDueToEnv?.includes('human_in_the_loop')) {
        toast('Saved, but the host is overriding it with HUMAN_IN_THE_LOOP', 'error')
      } else {
        toast(resolved
          ? 'Human review on — nothing publishes until you approve it'
          : 'Human review off — finished posts will publish themselves')
      }
      onRan()
    } catch {
      setPendingReview(null)
      toast('Could not reach the server', 'error')
    } finally {
      setSaving(false)
    }
  }, [onRan, toast])

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

  if (!state) return null

  const next = state.scheduled[0]

  // "Quiet" is measured against the engine's own cadence rather than a fixed
  // number of hours: an engine set to one post a week is not sick for being
  // silent on Tuesday. Two full gaps with nothing running means something is
  // wrong — the cron stopped, the worker is crashing on start, the host is down.
  const lastRun = state.lastRun ?? null
  const silent = state.enabled && (
    !lastRun || Date.now() - new Date(lastRun.at).getTime() > Math.max(state.gapHours, 1) * 2 * 3_600_000
  )
  // The dot pulsed unconditionally before, so a dead engine sat behind a pulsing
  // light. `motion.css` states the contract: a pulse means "live right now".
  const beating = state.enabled && !silent
  const vetoHours = settings?.vetoWindowHours ?? state.gapHours

  /** Switching review ON is the safe direction and takes effect immediately.
   *  Switching it OFF puts unread posts on a public website, so it goes through
   *  the dialog. The asymmetry is the point: friction belongs on the way out. */
  function onSwitch() {
    if (lockedByHost || saving) return
    if (reviewOn) setConfirmOff(true)
    else save(true)
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
            className={`dot dot--lg${beating ? ' pulse' : ''}`}
            style={{ color: !state.enabled ? 'var(--grey-dot)' : silent ? 'var(--rose)' : 'var(--lav-deep)' }}
            aria-hidden="true"
          />
          Autopilot {state.enabled ? 'on' : 'paused'}
        </span>

        {/* The heartbeat lives here, not in the sidebar's side-card, because
            that card is inside `.collapsible` and disappears below 900px — the
            engine's health was invisible on exactly the device the operator
            checks it from. This strip is on every viewport. */}
        <span
          className="t-base"
          style={{ color: silent ? 'var(--rose-ink)' : 'var(--ink-3)', fontWeight: silent ? 600 : 400 }}
        >
          {lastRun ? `Last tick ${relative(lastRun.at)}` : 'Never run'}
          {silent && ' · engine has gone quiet'}
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

      <div
        className="autonomy"
        data-review={reviewOn ? 'on' : 'off'}
        style={{ marginTop: 14, position: 'relative', zIndex: 1 }}
      >
        <button
          type="button"
          role="switch"
          className="switch"
          aria-checked={reviewOn}
          aria-labelledby="autonomy-state"
          aria-describedby="autonomy-detail"
          disabled={lockedByHost || saving}
          onClick={onSwitch}
        />
        <span style={{ minWidth: 0 }}>
          <span id="autonomy-state" className="autonomy-state">
            {reviewOn ? 'Human review on' : 'Human review off'}
          </span>
          <span id="autonomy-detail" className="t-sm muted" style={{ display: 'block', marginTop: 3 }}>
            {reviewOn
              ? `Every topic stops at the research and draft gates for you, and finished posts wait ${vetoHours}h before publishing.`
              : `Both gates auto-advance and finished posts publish themselves to the live site unread, one every ${state.gapHours}h.`}
          </span>
        </span>
      </div>

      {/* One live region for the whole control, so a screen reader hears the
          state change once rather than hearing the label re-read on every poll. */}
      <p className="sr-only" role="status" aria-live="polite">
        {reviewOn
          ? 'Human review is on. Posts wait for your approval.'
          : 'Human review is off. Posts publish to the live site without approval.'}
      </p>

      {pinned.length > 0 && (
        <p className="notice notice--amber t-sm" style={{ marginTop: 10 }}>
          Pinned on the server, not by this dashboard:{' '}
          {pinned.map((name, i) => (
            <span key={name}>{i > 0 && ', '}<code>{name}</code></span>
          ))}
          .{' '}
          {lockedByHost ? (
            <>
              The switch above is locked because of it, and the engine ignores what is saved here
              {typeof storedReview === 'boolean'
                ? ` (saved as review ${storedReview ? 'on' : 'off'})`
                : ''}
              . Unset it on the host to hand the switch back to this dashboard.
            </>
          ) : (
            <>Those values come from the environment; changing them here would have no effect.</>
          )}
        </p>
      )}

      {settings?.error && (
        <p className="notice notice--amber t-sm" style={{ marginTop: 10 }}>
          The settings row could not be read ({settings.error}), so the engine is holding every
          topic for review until it can. Run <code>python setup_db.py</code> if this is a fresh
          database.
        </p>
      )}

      <p className="t-sm muted" style={{ marginTop: 12, position: 'relative', zIndex: 1 }}>
        The hourly cron writes one topic per tick. Cadence is one post every {state.gapHours}h and
        does not change with this switch.
      </p>

      <Dialog
        open={confirmOff}
        onClose={() => setConfirmOff(false)}
        title="Publish without human review?"
        description="This changes what reaches the public site, so it is worth reading before you confirm."
        footer={
          <>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => setConfirmOff(false)}
            >
              Keep review on
            </button>
            <button
              type="button"
              className="btn btn--danger btn--sm"
              onClick={() => { setConfirmOff(false); save(false) }}
            >
              Switch review off
            </button>
          </>
        }
      >
        <ul className="t-base muted" style={{ margin: '14px 0 4px', paddingLeft: 18, lineHeight: 1.7 }}>
          <li>Both gates — research and draft — advance without you.</li>
          <li>Finished posts publish themselves to the live blog, unread by anyone.</li>
          <li>
            The {vetoHours}h veto window closes. A post can go out on the next tick rather than
            waiting for you to object.
          </li>
          <li>
            Cadence is unchanged: still one post every {state.gapHours}h, so the queue drips out
            rather than landing at once.
          </li>
          <li>A topic the auditor rejects twice is marked failed instead of published.</li>
        </ul>
      </Dialog>
    </section>
  )
}
