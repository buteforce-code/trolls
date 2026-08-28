'use client'

import { Suspense, useEffect, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import type { AgentEvent, AgentRun } from '../../lib/types'
import { duration, money, num, relative } from '../../lib/format'
import { usePoll } from '../../lib/use-poll'
import { PageHeader, EmptyState } from '../../components/ui/page-header'
import { RunDetail } from '../../components/swarm/run-detail'

interface SwarmPayload {
  runs: AgentRun[]
  last24h: { costUsd: number; inputTokens: number; outputTokens: number; runs: number }
  ceilings: { perRunUsd: number; perDayUsd: number }
}

/** Above this share of the daily ceiling the spend bar stops being informational. */
const HOT_THRESHOLD = 0.8

export default function SwarmPage() {
  return (
    <Suspense fallback={<SwarmSkeleton />}>
      <Swarm />
    </Suspense>
  )
}

function SwarmSkeleton() {
  return (
    <div aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading swarm telemetry</span>
      <div className="grid-stats mb-22">
        {[0, 1, 2].map(i => <div key={i} className="card card--tight" style={{ height: 140 }} />)}
      </div>
      <div className="card" style={{ height: 420 }} />
    </div>
  )
}

function Swarm() {
  const params = useSearchParams()
  const router = useRouter()

  const { data, error, loading } = usePoll<SwarmPayload>(
    '/api/swarm?limit=40',
    payload => payload.runs.some(r => r.status === 'running'),
    { activeMs: 4000, idleMs: 20_000 },
  )

  const runs = data?.runs ?? []
  const selectedId = params.get('run') ?? runs[0]?.id ?? null
  const selected = runs.find(r => r.id === selectedId) ?? runs[0] ?? null

  const [events, setEvents] = useState<AgentEvent[]>([])
  const [eventsLoading, setEventsLoading] = useState(false)

  // Keyed on the run id and nothing else. `selected` is derived from `data`,
  // and `usePoll` hands back a freshly parsed object every 4s — so including it
  // here re-fired this effect on every poll, blanking the roster back to
  // `waiting`, replacing the stream with its loading state, and collapsing the
  // panel from ~430px to ~40px before the refetch landed. On the one page whose
  // whole job is watching a live run, that is the flicker DESIGN_BRIEF.md §7
  // names as a hard constraint. Clearing is correct *here* because the effect
  // now runs only when the operator actually picks a different run.
  const runId = selected?.id ?? null
  useEffect(() => {
    if (!runId) return
    let cancelled = false
    setEventsLoading(true)
    setEvents([])
    fetch(`/api/swarm/${runId}`, { headers: { accept: 'application/json' } })
      .then(r => (r.ok ? r.json() : null))
      .then(payload => { if (payload && !cancelled) setEvents(payload.events ?? []) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setEventsLoading(false) })
    return () => { cancelled = true }
  }, [runId])

  const meters = useMemo(() => {
    const spend = data?.last24h.costUsd ?? 0
    const ceiling = data?.ceilings.perDayUsd || 1
    return {
      spend,
      ceiling,
      share: Math.min(1, spend / ceiling),
      hot: spend / ceiling >= HOT_THRESHOLD,
      runs: data?.last24h.runs ?? 0,
      average: data?.last24h.runs ? spend / data.last24h.runs : 0,
      inputTokens: data?.last24h.inputTokens ?? 0,
      outputTokens: data?.last24h.outputTokens ?? 0,
    }
  }, [data])

  if (loading && !data) return <SwarmSkeleton />

  return (
    <div className="view-enter">
      <PageHeader
        title="Swarm"
        subtitle="Ten agents and two gates, live. Every call is timed, tokened and costed."
      />

      {error && (
        <p className="notice notice--rose mb-22" role="alert">Could not load telemetry: {error}</p>
      )}

      <div className="grid-stats mb-22">
        <section className="card card--tight rise spotlight" style={{ '--i': 0 } as React.CSSProperties}>
          <p className="t-base muted" style={{ position: 'relative', zIndex: 1 }}>Spend · last 24h</p>
          <p
            className="stat-value stat-value--sm"
            style={{ margin: '8px 0 14px', position: 'relative', zIndex: 1 }}
          >
            {money(meters.spend, 2)}
          </p>
          <div className="track track--thin" style={{ position: 'relative', zIndex: 1 }}>
            <div
              className="track-fill bar-grow-x"
              style={{
                width: `${meters.share * 100}%`,
                background: meters.hot ? 'var(--rose)' : 'var(--lav-deep)',
              }}
            />
          </div>
          <p className="t-sm" style={{ color: 'var(--ink-mute)', marginTop: 10, lineHeight: 1.5, position: 'relative', zIndex: 1 }}>
            {meters.hot && <strong style={{ color: 'var(--rose-ink)' }}>Near the ceiling. </strong>}
            ceiling {money(meters.ceiling, 2)}/day · {money(data?.ceilings.perRunUsd ?? 0, 2)}/run —
            checked before each call, not after.
          </p>
        </section>

        <section className="card card--tight rise spotlight" style={{ '--i': 1 } as React.CSSProperties}>
          <p className="t-base muted" style={{ position: 'relative', zIndex: 1 }}>Runs · last 24h</p>
          <p className="stat-value stat-value--sm" style={{ margin: '8px 0 10px', position: 'relative', zIndex: 1 }}>
            {meters.runs}
          </p>
          <p className="t-sm" style={{ color: 'var(--ink-mute)', position: 'relative', zIndex: 1 }}>
            {meters.runs ? `${money(meters.average)} average` : 'nothing has run today'}
          </p>
        </section>

        <section className="card card--tight rise spotlight" style={{ '--i': 2 } as React.CSSProperties}>
          <p className="t-base muted" style={{ position: 'relative', zIndex: 1 }}>Tokens · last 24h</p>
          <p className="stat-value stat-value--sm" style={{ margin: '8px 0 10px', position: 'relative', zIndex: 1 }}>
            {num(meters.inputTokens + meters.outputTokens)}
          </p>
          <p className="t-sm" style={{ color: 'var(--ink-mute)', position: 'relative', zIndex: 1 }}>
            {num(meters.inputTokens)} in · {num(meters.outputTokens)} out
          </p>
        </section>
      </div>

      {runs.length === 0 ? (
        <EmptyState
          title="No runs recorded yet"
          hint="Telemetry starts filling in the moment the first agent executes. Brief a topic from the pipeline to see one."
        />
      ) : (
        <div className="row wrap gap-22" style={{ alignItems: 'flex-start' }}>
          <div
            className="stack gap-10 rise"
            style={{ flex: '1 1 290px', maxWidth: 340, minWidth: 270, '--i': 2 } as React.CSSProperties}
          >
            <h2 className="section-title" style={{ fontSize: 16, padding: '0 2px 4px' }}>Runs</h2>
            {runs.map(run => {
              const tone = run.status === 'failed' ? 'chip--rose' : run.status === 'running' ? 'chip--lav' : 'chip--grey'
              return (
                <button
                  key={run.id}
                  type="button"
                  className="list-row"
                  data-active={run.id === selected?.id}
                  aria-current={run.id === selected?.id ? 'true' : undefined}
                  onClick={() => router.replace(`/swarm?run=${run.id}`, { scroll: false })}
                >
                  <span className="row" style={{ justifyContent: 'space-between', gap: 10 }}>
                    <span className={`chip ${tone}`}>
                      {run.status === 'running' && <span className="dot pulse pulse--fast" aria-hidden="true" />}
                      {run.status}
                    </span>
                    <span className="mono t-sm" style={{ color: 'var(--ink-2)' }}>
                      {money(Number(run.total_cost_usd ?? 0))}
                    </span>
                  </span>
                  <span className="truncate t-base" style={{ fontWeight: 600, display: 'block' }}>
                    {run.topic_slug || 'untitled run'}
                  </span>
                  <span className="mono t-xs" style={{ color: 'var(--ink-mute)' }}>
                    {relative(run.started_at)} · {run.agent_count ?? 0} agent{run.agent_count === 1 ? '' : 's'}
                    {run.duration_ms ? ` · ${duration(run.duration_ms)}` : ' · running'}
                  </span>
                </button>
              )
            })}
          </div>

          {selected && <RunDetail run={selected} events={events} loading={eventsLoading} />}
        </div>
      )}
    </div>
  )
}
