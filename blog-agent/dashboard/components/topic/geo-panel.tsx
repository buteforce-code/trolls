'use client'

import type { AgentEvent } from '../../lib/types'
import { num } from '../../lib/format'

/**
 * The GEO template gate, reported from what actually happened.
 *
 * The six requirements below are the real ones — they mirror `swarm/geo.py`,
 * which is the module that decides whether a post is allowed to ship. What this
 * panel deliberately does NOT do is claim per-requirement pass/fail that the
 * database cannot support: the gate records one event per attempt with a
 * pipe-joined failure string, not six booleans. So a requirement is marked
 * "Repair" only when its own text appears in a real rejection reason, "Pass"
 * only when the gate genuinely passed, and "Not run" otherwise.
 *
 * The honest version of this panel is less colourful than the mock-up. It is
 * also the only version an operator can act on.
 */

interface Requirement {
  n: string
  title: string
  how: string
  /** Words that identify this requirement inside a gate failure string. */
  match: readonly string[]
}

const REQUIREMENTS: readonly Requirement[] = [
  {
    n: '1',
    title: 'Question-form H2s with a self-contained answer',
    how: '≥2 headings · 40–160 words of prose, first block under the heading',
    match: ['heading', 'h2', 'question', 'answer'],
  },
  {
    n: '2',
    title: 'Unrounded proof numbers, zero puffery',
    how: 'Canonical proof numbers from the brand profile, no adjective standing in for a number',
    match: ['proof number', 'puffery', 'adjective', 'number'],
  },
  {
    n: '3',
    title: 'Competitor-inclusive comparison table',
    how: '≥2 named rivals · ≥3 rows · an honest “where they win” column',
    match: ['competitor', 'table', 'comparison'],
  },
  {
    n: '4',
    title: 'An explicit “not a fit if…” section',
    how: '≥40 words, several accepted phrasings',
    match: ['not a fit', 'disqualif'],
  },
  {
    n: '5',
    title: 'Visible dateModified',
    how: 'Injected deterministically, then asserted',
    match: ['datemodified', 'date modified'],
  },
  {
    n: '6',
    title: 'Named author',
    how: 'Injected deterministically, then asserted',
    match: ['author'],
  },
]

const LENGTH_FLOOR = 1100
const LENGTH_TARGET = 1450

type Verdict = 'passed' | 'failed' | 'pending'

const VERDICT_STYLE: Record<Verdict, { bg: string; ink: string; badge: string }> = {
  passed:  { bg: 'var(--teal-tint)', ink: 'var(--teal-ink)', badge: 'Pass' },
  failed:  { bg: 'var(--rose-tint)', ink: 'var(--rose-ink)', badge: 'Repair' },
  pending: { bg: 'var(--bg)',        ink: 'var(--ink-mute)', badge: 'Not run' },
}

function reasonOf(event: AgentEvent): string {
  const detail = event.detail as { reason?: unknown } | null
  return typeof detail?.reason === 'string' ? detail.reason : ''
}

export function GeoPanel({ events, wordCount }: { events: readonly AgentEvent[]; wordCount: number }) {
  const geoEvents = events.filter(e => e.agent === 'geo_gate')
  const lengthEvents = events.filter(e => e.agent === 'length_gate')

  const lastGeo = geoEvents[geoEvents.length - 1]
  const geoRan = geoEvents.length > 0
  const geoPassed = lastGeo?.kind === 'gate_passed'
  const failureText = geoEvents
    .filter(e => e.kind === 'gate_rejected')
    .map(reasonOf)
    .join(' | ')
    .toLowerCase()

  const rows = REQUIREMENTS.map(req => {
    let verdict: Verdict = 'pending'
    if (geoRan) {
      const named = req.match.some(m => failureText.includes(m))
      verdict = named && !geoPassed ? 'failed' : geoPassed ? 'passed' : 'pending'
    }
    return { req, verdict }
  })

  const failedCount = rows.filter(r => r.verdict === 'failed').length
  const attempts = geoEvents.length
  const lengthPassed = lengthEvents.length > 0 && lengthEvents[lengthEvents.length - 1].kind === 'gate_passed'
  const lengthRan = lengthEvents.length > 0
  const belowFloor = wordCount > 0 && wordCount < LENGTH_FLOOR

  const verdictStyle = !geoRan
    ? { bg: 'var(--bg)', ink: 'var(--ink-3)' }
    : geoPassed
      ? { bg: 'var(--teal-tint)', ink: 'var(--teal-ink)' }
      : { bg: 'var(--rose-tint)', ink: 'var(--rose-ink)' }

  return (
    <>
      <div
        className="row wrap gap-14 mb-22"
        style={{ background: verdictStyle.bg, borderRadius: 'var(--r-lg)', padding: '18px 20px' }}
      >
        <span className="display" style={{ fontWeight: 600, fontSize: 16, color: verdictStyle.ink }}>
          {!geoRan
            ? 'Gate has not run yet'
            : geoPassed
              ? 'The gate passed on the artefact that shipped'
              : `${failedCount || 'Some'} requirement${failedCount === 1 ? '' : 's'} to repair`}
        </span>
        <span className="chip" style={{ background: '#fff', color: verdictStyle.ink }}>
          {attempts} assertion{attempts === 1 ? '' : 's'}
        </span>
        <span className="t-base" style={{ color: verdictStyle.ink, opacity: .86, flex: 1, minWidth: 220, lineHeight: 1.55 }}>
          {geoRan
            ? 'Re-asserted after the writer, after the humaniser, and on the exact artefact that ships. A second failure holds the topic for a human — it never publishes.'
            : 'The gate runs three times per post, after the writer, after the humaniser, and on the final artefact.'}
        </span>
      </div>

      <ul className="stack gap-10 mb-22" style={{ listStyle: 'none' }}>
        {rows.map(({ req, verdict }) => {
          const style = VERDICT_STYLE[verdict]
          return (
            <li
              key={req.n}
              className="row gap-14"
              style={{
                alignItems: 'flex-start',
                border: '1px solid var(--line)',
                borderRadius: 'var(--r-md)',
                padding: '15px 17px',
              }}
            >
              <span
                className="display"
                style={{
                  width: 26, height: 26, flex: 'none',
                  borderRadius: 9,
                  background: style.bg, color: style.ink,
                  display: 'grid', placeItems: 'center',
                  fontWeight: 600, fontSize: 12.5,
                }}
                aria-hidden="true"
              >
                {req.n}
              </span>
              <span style={{ minWidth: 0, flex: 1 }}>
                <span className="pretty" style={{ display: 'block', fontWeight: 600, fontSize: 'var(--text-md)', lineHeight: 1.4 }}>
                  {req.title}
                </span>
                <span className="t-sm" style={{ display: 'block', color: 'var(--ink-mute)', marginTop: 5, lineHeight: 1.5 }}>
                  {req.how}
                </span>
              </span>
              <span className="chip" style={{ flex: 'none', background: style.bg, color: style.ink }}>
                {style.badge}
              </span>
            </li>
          )
        })}
      </ul>

      {!geoPassed && failureText && (
        <div className="notice notice--rose mb-22">
          <span style={{ flex: 1, minWidth: 200 }}>
            <strong style={{ display: 'block', marginBottom: 4 }}>What the gate said</strong>
            <span className="mono t-sm">{failureText}</span>
          </span>
        </div>
      )}

      <div style={{ border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', padding: '20px 22px' }}>
        <div className="row wrap gap-12" style={{ marginBottom: 14 }}>
          <h2 className="section-title" style={{ fontSize: 16 }}>Length gate</h2>
          <span
            className={`chip ${!lengthRan ? 'chip--grey' : lengthPassed && !belowFloor ? 'chip--teal' : 'chip--rose'}`}
          >
            {!lengthRan ? 'Not run' : belowFloor ? 'Below the floor' : 'Above the floor'}
          </span>
          <span className="display tnum push" style={{ fontWeight: 700, fontSize: 22 }}>
            {num(wordCount)}
            <span className="t-base" style={{ fontWeight: 500, color: 'var(--ink-mute)' }}> words</span>
          </span>
        </div>

        <div className="track track--thin" style={{ marginBottom: 9 }}>
          <div
            className="track-fill bar-grow-x"
            style={{
              width: `${Math.min(100, (wordCount / LENGTH_TARGET) * 100)}%`,
              background: belowFloor ? 'var(--rose)' : 'var(--lav-deep)',
            }}
          />
        </div>
        <div className="row t-sm faint" style={{ justifyContent: 'space-between', marginBottom: 13 }}>
          <span>floor {num(LENGTH_FLOOR)}</span>
          <span>target {num(LENGTH_TARGET)}</span>
        </div>
        <p className="t-base" style={{ lineHeight: 1.65, color: 'var(--ink-2)' }}>
          A short draft is re-asked section by section rather than rewritten whole — a whole-post
          re-ask anchors to the short version and barely moves. The gate splits the body at
          <code className="mono"> ## </code> and expands the thinnest section until it clears the target.
        </p>
      </div>
    </>
  )
}
