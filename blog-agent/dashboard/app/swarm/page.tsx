'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Live swarm view.
 *
 * Three questions this answers that raw stdout never could: which agent is
 * working right now, what did each one cost, and where did a gate reject the
 * draft. The gate rejections are the point — a prospect watching the pipeline
 * refuse to publish a thin post is the most persuasive thing this product does.
 */

type Run = {
  id: string
  topic_slug: string | null
  trigger: string | null
  status: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  total_input_tokens: number | null
  total_output_tokens: number | null
  total_cost_usd: number | string | null
  agent_count: number | null
  error: string | null
}

type SwarmEvent = {
  id: number
  seq: number
  agent: string | null
  kind: string
  detail: Record<string, unknown> | null
  input_tokens: number | null
  output_tokens: number | null
  cost_usd: number | string | null
  duration_ms: number | null
  at: string | null
}

type Ceilings = { perRunUsd: number; perDayUsd: number }
type Last24h = { costUsd: number; inputTokens: number; outputTokens: number; runs: number }

const POLL_MS = 3000

// Every agent in the swarm, in pipeline order, so the roster reads as a machine
// rather than as whatever happened to run. Kept here rather than derived from
// events so agents that have not started yet are still visible as "waiting".
const AGENT_ORDER = [
  'ideator_agent',
  'research_agent',
  'audit_agent',
  'content_writer_agent',
  'humaniser_agent',
  'image_planner_agent',
  'linker_agent',
  'schema_faq_agent',
  'social_agent',
  'publisher_agent',
]

const AGENT_LABELS: Record<string, string> = {
  ideator_agent: 'Ideator',
  research_agent: 'Research',
  audit_agent: 'Auditor',
  content_writer_agent: 'Writer',
  humaniser_agent: 'Humaniser',
  image_planner_agent: 'Imager',
  linker_agent: 'Linker',
  schema_faq_agent: 'Schema',
  social_agent: 'Social',
  publisher_agent: 'Publisher',
  geo_gate: 'GEO gate',
  length_gate: 'Length gate',
}

const label = (agent: string | null): string => (agent ? AGENT_LABELS[agent] || agent : '—')

const num = (value: number | string | null | undefined): number => Number(value || 0)

const money = (value: number | string | null | undefined): string => `$${num(value).toFixed(4)}`

const secs = (ms: number | null | undefined): string =>
  ms ? `${(ms / 1000).toFixed(1)}s` : '—'

const clock = (iso: string | null): string =>
  iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''

function agentState(events: SwarmEvent[], agent: string): 'done' | 'running' | 'failed' | 'waiting' {
  const mine = events.filter(e => e.agent === agent)
  if (mine.some(e => e.kind === 'agent_failed')) return 'failed'
  if (mine.some(e => e.kind === 'agent_finished')) return 'done'
  if (mine.some(e => e.kind === 'agent_started')) return 'running'
  return 'waiting'
}

export default function SwarmPage() {
  const [runs, setRuns] = useState<Run[]>([])
  const [last24h, setLast24h] = useState<Last24h | null>(null)
  const [ceilings, setCeilings] = useState<Ceilings | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [events, setEvents] = useState<SwarmEvent[]>([])
  const [activeRun, setActiveRun] = useState<Run | null>(null)
  const [loading, setLoading] = useState(true)
  const streamRef = useRef<HTMLDivElement>(null)

  const loadRuns = useCallback(async () => {
    try {
      const res = await fetch('/api/swarm', { cache: 'no-store' })
      if (!res.ok) return
      const data = await res.json()
      setRuns(data.runs || [])
      setLast24h(data.last24h || null)
      setCeilings(data.ceilings || null)
      setSelected(prev => prev ?? (data.runs?.[0]?.id || null))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadEvents = useCallback(async (runId: string) => {
    const res = await fetch(`/api/swarm/${runId}`, { cache: 'no-store' })
    if (!res.ok) return
    const data = await res.json()
    setEvents(data.events || [])
    setActiveRun(data.run || null)
  }, [])

  useEffect(() => {
    loadRuns()
    const id = setInterval(loadRuns, POLL_MS)
    return () => clearInterval(id)
  }, [loadRuns])

  useEffect(() => {
    if (!selected) return
    loadEvents(selected)
    const id = setInterval(() => loadEvents(selected), POLL_MS)
    return () => clearInterval(id)
  }, [selected, loadEvents])

  // Follow the tail while a run is live, but leave scroll alone once it ends so
  // a finished run can be read from the top.
  useEffect(() => {
    if (activeRun?.status === 'running' && streamRef.current) {
      streamRef.current.scrollTop = streamRef.current.scrollHeight
    }
  }, [events, activeRun?.status])

  const dayPct = last24h && ceilings?.perDayUsd
    ? Math.min(100, (last24h.costUsd / ceilings.perDayUsd) * 100)
    : 0

  return (
    <main className="container" style={{ paddingTop: 32, paddingBottom: 64 }}>
      <div className="page-header">
        <div className="page-header-row">
          <div>
            <h1 className="pipeline-title">Swarm</h1>
            <p className="field-hint">
              Ten agents and two gates, live. Every call is timed, tokened and costed.
            </p>
          </div>
          <a className="btn btn-outline btn-sm" href="/">← Topics</a>
        </div>
      </div>

      {last24h && ceilings ? (
        <section className="swarm-meters">
          <div className="swarm-meter">
            <span className="swarm-meter-label">Spend · last 24h</span>
            <strong className="swarm-meter-value">{money(last24h.costUsd)}</strong>
            <div className="swarm-bar" role="img"
                 aria-label={`${dayPct.toFixed(0)}% of the daily ceiling used`}>
              <div className={`swarm-bar-fill${dayPct > 80 ? ' is-hot' : ''}`}
                   style={{ width: `${dayPct}%` }} />
            </div>
            <span className="swarm-meter-foot">
              ceiling ${ceilings.perDayUsd.toFixed(2)}/day · ${ceilings.perRunUsd.toFixed(2)}/run
            </span>
          </div>
          <div className="swarm-meter">
            <span className="swarm-meter-label">Runs · last 24h</span>
            <strong className="swarm-meter-value">{last24h.runs}</strong>
            <span className="swarm-meter-foot">
              {last24h.runs ? money(last24h.costUsd / last24h.runs) : '$0.0000'} average
            </span>
          </div>
          <div className="swarm-meter">
            <span className="swarm-meter-label">Tokens · last 24h</span>
            <strong className="swarm-meter-value">
              {(last24h.inputTokens + last24h.outputTokens).toLocaleString()}
            </strong>
            <span className="swarm-meter-foot">
              {last24h.inputTokens.toLocaleString()} in · {last24h.outputTokens.toLocaleString()} out
            </span>
          </div>
        </section>
      ) : null}

      <div className="swarm-layout">
        <aside className="swarm-runs">
          <h2 className="swarm-section-title">Runs</h2>
          {loading ? <p className="field-hint">Loading…</p> : null}
          {!loading && runs.length === 0 ? (
            <p className="field-hint">
              No recorded runs yet. Start a topic, or wait for the next autopilot tick.
            </p>
          ) : null}
          {runs.map(run => (
            <button
              key={run.id}
              className={`swarm-run${selected === run.id ? ' is-selected' : ''}`}
              onClick={() => { setSelected(run.id); setEvents([]) }}
            >
              <span className="swarm-run-top">
                <span className={`badge badge-${run.status === 'succeeded' ? 'published' : run.status === 'failed' ? 'failed' : 'writing'}`}>
                  {run.status}
                </span>
                <span className="mono swarm-run-cost">{money(run.total_cost_usd)}</span>
              </span>
              <span className="swarm-run-slug">{run.topic_slug || 'untitled'}</span>
              <span className="swarm-run-meta mono">
                {clock(run.started_at)} · {run.agent_count || 0} agents · {secs(run.duration_ms)}
              </span>
            </button>
          ))}
        </aside>

        <section className="swarm-detail">
          {activeRun ? (
            <>
              <div className="swarm-roster">
                {AGENT_ORDER.map(agent => {
                  const state = agentState(events, agent)
                  return (
                    <span key={agent} className={`swarm-chip is-${state}`} title={agent}>
                      {label(agent)}
                    </span>
                  )
                })}
              </div>

              {activeRun.error ? (
                <div className="swarm-error" role="alert">
                  <strong>Run failed</strong>
                  <span className="mono">{activeRun.error}</span>
                </div>
              ) : null}

              <h2 className="swarm-section-title">Event stream</h2>
              <div className="swarm-stream" ref={streamRef}>
                {events.length === 0 ? (
                  <p className="field-hint" style={{ padding: 16 }}>
                    No events recorded for this run.
                  </p>
                ) : null}
                {events.map(event => {
                  const reason = (event.detail?.reason as string) || (event.detail?.error as string) || ''
                  return (
                    <div key={event.id} className={`swarm-event kind-${event.kind}`}>
                      <span className="swarm-event-seq mono">{String(event.seq).padStart(2, '0')}</span>
                      <span className="swarm-event-agent">{label(event.agent)}</span>
                      <span className="swarm-event-kind mono">{event.kind.replace(/_/g, ' ')}</span>
                      <span className="swarm-event-nums mono">
                        {event.duration_ms ? secs(event.duration_ms) : ''}
                        {num(event.input_tokens) || num(event.output_tokens)
                          ? ` · ${num(event.input_tokens)}in/${num(event.output_tokens)}out`
                          : ''}
                        {num(event.cost_usd) ? ` · ${money(event.cost_usd)}` : ''}
                      </span>
                      {reason ? <span className="swarm-event-reason">{reason}</span> : null}
                    </div>
                  )
                })}
              </div>
            </>
          ) : (
            <p className="field-hint">Select a run to inspect it.</p>
          )}
        </section>
      </div>
    </main>
  )
}
