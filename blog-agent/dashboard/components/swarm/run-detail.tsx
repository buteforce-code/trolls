'use client'

import type { AgentEvent, AgentRun } from '../../lib/types'
import { duration, money, num, seconds } from '../../lib/format'

/** Machine name → the name a person would use in conversation. */
export const AGENT_LABELS: Record<string, string> = {
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

const ROSTER = Object.keys(AGENT_LABELS)

type AgentState = 'done' | 'running' | 'failed' | 'skipped' | 'waiting'

const STATE_TONE: Record<AgentState, string> = {
  done: 'chip--teal',
  running: 'chip--lav',
  failed: 'chip--rose',
  skipped: 'chip--grey',
  waiting: 'chip--grey',
}

const KIND_TONE: Record<string, string> = {
  agent_started: 'chip--lav',
  agent_finished: 'chip--grey',
  agent_failed: 'chip--rose',
  // A retry is not a failure and not a success — it is the pipeline absorbing a
  // transient provider fault. Worth seeing (three of them in a row is a story),
  // not worth the alarm colour.
  agent_retry: 'chip--amber',
  agent_skipped: 'chip--grey',
  tool_call: 'chip--grey',
  gate_passed: 'chip--teal',
  gate_rejected: 'chip--rose',
  run_failed: 'chip--rose',
}

function stateOf(agent: string, events: readonly AgentEvent[]): AgentState {
  const mine = events.filter(e => e.agent === agent)
  if (mine.length === 0) return 'waiting'
  if (mine.some(e => e.kind === 'agent_failed' || e.kind === 'gate_rejected')) return 'failed'
  if (mine.some(e => e.kind === 'agent_skipped')) return 'skipped'
  if (mine.some(e => e.kind === 'agent_finished' || e.kind === 'gate_passed')) return 'done'
  return 'running'
}

function reasonOf(event: AgentEvent): string {
  const detail = event.detail as { reason?: unknown } | null
  return typeof detail?.reason === 'string' ? detail.reason : ''
}

function numbersOf(event: AgentEvent): string {
  const cost = Number(event.cost_usd ?? 0)
  return [
    event.duration_ms ? seconds(event.duration_ms) : '',
    (event.input_tokens || event.output_tokens)
      ? `${num(event.input_tokens ?? 0)} in / ${num(event.output_tokens ?? 0)} out`
      : '',
    cost ? money(cost) : '',
  ].filter(Boolean).join(' · ')
}

interface Props {
  run: AgentRun
  events: readonly AgentEvent[]
  loading: boolean
}

export function RunDetail({ run, events, loading }: Props) {
  const summary = run.status === 'running'
    ? 'Running now'
    : run.status === 'failed'
      ? `Failed · ${duration(run.duration_ms)}`
      : `Succeeded · ${duration(run.duration_ms)} · ${money(Number(run.total_cost_usd ?? 0))}`

  return (
    <section
      className="card rise"
      style={{ flex: '2.4 1 460px', minWidth: 320, '--i': 3 } as React.CSSProperties}
      aria-label="Selected run"
    >
      <div className="row wrap gap-14 mb-18" style={{ alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div style={{ minWidth: 0 }}>
          <h2 className="section-title truncate" style={{ fontSize: 'var(--text-lg)' }}>
            {run.topic_slug || 'untitled run'}
          </h2>
          <p className="mono t-sm" style={{ color: 'var(--ink-mute)', marginTop: 5 }}>
            {run.id} · {run.trigger || 'manual'}
          </p>
        </div>
        <p className="t-base muted">{summary}</p>
      </div>

      <ul className="row wrap gap-8 mb-22" style={{ listStyle: 'none' }} aria-label="Agent roster">
        {ROSTER.map(agent => {
          const state = stateOf(agent, events)
          return (
            <li
              key={agent}
              className={`chip ${STATE_TONE[state]}${state === 'waiting' ? ' chip--dashed' : ''}`}
            >
              <span className={`dot${state === 'running' ? ' pulse pulse--fast' : ''}`} aria-hidden="true" />
              {AGENT_LABELS[agent]}
              <span className="sr-only"> — {state}</span>
            </li>
          )
        })}
      </ul>

      {run.error && (
        <div className="notice notice--rose mb-18">
          <span style={{ flex: 1, minWidth: 200 }}>
            <strong style={{ display: 'block', marginBottom: 5 }}>Run failed</strong>
            <span className="mono t-sm">{run.error}</span>
          </span>
        </div>
      )}

      <p className="t-sm" style={{ color: 'var(--ink-mute)', fontWeight: 500, marginBottom: 8 }}>
        Event stream
      </p>

      <div
        className="scroller"
        style={{
          maxHeight: 430,
          background: 'var(--surface-sunk)',
          border: '1px solid var(--chip)',
          borderRadius: 'var(--r-lg)',
          padding: 8,
        }}
      >
        {loading && events.length === 0 && (
          <p className="t-base muted" style={{ padding: 12 }}>Loading the stream…</p>
        )}
        {!loading && events.length === 0 && (
          <p className="t-base muted" style={{ padding: 12 }}>
            No events recorded for this run.
          </p>
        )}
        {events.map(event => {
          const reason = reasonOf(event)
          const numbers = numbersOf(event)
          const isRejection = event.kind === 'gate_rejected' || event.kind === 'agent_failed' || event.kind === 'run_failed'
          return (
            <div
              key={event.id}
              className="event"
              style={isRejection
                ? { background: 'var(--rose-tint)', boxShadow: 'inset 3px 0 0 var(--rose)' }
                : undefined}
            >
              <span className="mono t-xs faint">{String(event.seq).padStart(2, '0')}</span>
              <span className="truncate t-base" style={{ fontWeight: 600 }}>
                {AGENT_LABELS[event.agent ?? ''] ?? event.agent ?? '—'}
              </span>
              <span className={`chip ${KIND_TONE[event.kind] ?? 'chip--grey'} mono t-xs`} style={{ justifySelf: 'start' }}>
                {event.kind.replace(/_/g, ' ')}
              </span>
              <span style={{ minWidth: 0 }}>
                {numbers && <span className="mono t-xs muted" style={{ display: 'block' }}>{numbers}</span>}
                {reason && (
                  <span className="t-sm" style={{ display: 'block', marginTop: 3, color: 'var(--ink-2)', lineHeight: 1.5 }}>
                    {reason}
                  </span>
                )}
              </span>
            </div>
          )
        })}
      </div>

      <p className="t-sm faint" style={{ marginTop: 12, lineHeight: 1.55 }}>
        Costs use list prices captured at build time — good enough to bound spend and compare
        agents against each other, not billing-grade.
      </p>
    </section>
  )
}
