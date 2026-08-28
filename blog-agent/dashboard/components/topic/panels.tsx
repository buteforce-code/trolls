'use client'

import type { BlogPost } from '../../lib/types'
import { num } from '../../lib/format'
import { CopyButton } from '../ui/copy-button'
import { EmptyState } from '../ui/page-header'

/* ── Research digest ─────────────────────────────────────────────────────── */

export interface Digest {
  topic?: string
  summary?: string
  what_people_say?: string
  buteforce_angle?: string
  key_facts?: string[]
  source_signals?: Record<string, string>
  confidence?: number
  _parse_error?: string
  raw?: string
}

export interface Audit {
  passed?: boolean
  score?: number
  recommendation?: string
  summary?: string
  fact_issues?: string[]
  seo_issues?: string[]
  angle_issues?: string[]
  dedup_risk?: string
  icp_fit?: string
}

/** Parse a jsonb/text column without letting one bad row take down the page. */
export function parseJson<T>(value: unknown): T | null {
  if (!value) return null
  if (typeof value === 'object') return value as T
  if (typeof value !== 'string') return null
  try { return JSON.parse(value) as T } catch { return null }
}

export function MonitorPanel({ digest, audit }: { digest: Digest | null; audit: Audit | null }) {
  if (!digest) {
    return (
      <EmptyState
        title="No research yet"
        hint="The research agent writes its digest here once it has swept the nine sources. Nothing is lost while it runs."
      />
    )
  }

  // A digest that failed to parse is the single most useful failure to surface:
  // it means the model returned prose where JSON was required, and every
  // downstream stage inherited garbage.
  if (digest._parse_error || !digest.summary) {
    return (
      <>
        <div className="notice notice--amber mb-18">
          <span style={{ flex: 1, minWidth: 200 }}>
            {digest._parse_error
              ? `The research agent's output could not be parsed: ${digest._parse_error}.`
              : 'The research agent returned no summary.'}{' '}
            The raw response is below — the writer worked from this.
          </span>
        </div>
        {digest.raw && <pre className="code scroller" style={{ maxHeight: 420 }}>{digest.raw}</pre>}
      </>
    )
  }

  const sources = Object.entries(digest.source_signals ?? {})

  return (
    <>
      {digest.buteforce_angle && (
        <div style={{ background: 'var(--lav-tint)', borderRadius: 'var(--r-lg)', padding: '20px 22px', marginBottom: 22 }}>
          <p className="t-sm" style={{ color: 'var(--lav-ink)', fontWeight: 600, marginBottom: 8 }}>
            The ButeForce angle · India-first
          </p>
          <p style={{ fontSize: 16, lineHeight: 1.6, color: '#241546' }}>{digest.buteforce_angle}</p>
        </div>
      )}

      <div className="grid-halves" style={{ gap: 26 }}>
        <div>
          <h3 className="t-sm" style={{ color: 'var(--ink-mute)', marginBottom: 10, fontWeight: 500 }}>Summary</h3>
          <p style={{ fontSize: 'var(--text-md)', lineHeight: 1.65, marginBottom: 18, color: 'var(--ink-2)' }}>
            {digest.summary || digest.topic}
          </p>
          <div className="row wrap" style={{ gap: 26 }}>
            {typeof digest.confidence === 'number' && (
              <div>
                <div className="display" style={{ fontWeight: 700, fontSize: 23, color: 'var(--lav-ink)' }}>
                  {digest.confidence.toFixed(2)}
                </div>
                <div className="t-sm" style={{ color: 'var(--ink-mute)', marginTop: 3 }}>confidence</div>
              </div>
            )}
            {sources.length > 0 && (
              <div>
                <div className="display" style={{ fontWeight: 700, fontSize: 23 }}>{sources.length}</div>
                <div className="t-sm" style={{ color: 'var(--ink-mute)', marginTop: 3 }}>sources</div>
              </div>
            )}
          </div>
        </div>

        {(digest.key_facts?.length ?? 0) > 0 && (
          <div>
            <h3 className="t-sm" style={{ color: 'var(--ink-mute)', marginBottom: 10, fontWeight: 500 }}>Key facts</h3>
            <ul style={{ listStyle: 'none' }}>
              {digest.key_facts!.map((fact, i) => (
                <li key={i} className="row gap-10" style={{ alignItems: 'flex-start', marginBottom: 12 }}>
                  <span
                    className="dot"
                    style={{ background: 'var(--lav)', color: 'var(--lav)', marginTop: 7 }}
                    aria-hidden="true"
                  />
                  <span className="t-base" style={{ lineHeight: 1.55, color: 'var(--ink-2)' }}>{fact}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {digest.what_people_say && (
        <>
          <hr className="divider" />
          <h3 className="t-sm" style={{ color: 'var(--ink-mute)', marginBottom: 10, fontWeight: 500 }}>
            What people are actually saying
          </h3>
          <p style={{ fontSize: 'var(--text-md)', lineHeight: 1.65, color: 'var(--ink-2)' }}>
            {digest.what_people_say}
          </p>
        </>
      )}

      {sources.length > 0 && (
        <>
          <hr className="divider" />
          <h3 className="t-sm" style={{ color: 'var(--ink-mute)', marginBottom: 12, fontWeight: 500 }}>
            Source signals
          </h3>
          <div className="grid-cards" style={{ gap: 10 }}>
            {sources.map(([name, text]) => (
              <div key={name} className="card card--sunk" style={{ padding: '13px 15px', borderRadius: 'var(--r-md)' }}>
                <p
                  className="t-xs mono"
                  style={{ fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--lav-ink)' }}
                >
                  {name}
                </p>
                <p className="t-sm" style={{ color: 'var(--ink-3)', lineHeight: 1.55, marginTop: 6 }}>{String(text)}</p>
              </div>
            ))}
          </div>
        </>
      )}

      {audit && typeof audit.score === 'number' && <AuditBlock audit={audit} />}
    </>
  )
}

function AuditBlock({ audit }: { audit: Audit }) {
  const passed = audit.passed ?? audit.recommendation === 'proceed'
  const issues = [
    ...(audit.fact_issues ?? []).map(t => ({ kind: 'Fact', text: t })),
    ...(audit.seo_issues ?? []).map(t => ({ kind: 'SEO', text: t })),
    ...(audit.angle_issues ?? []).map(t => ({ kind: 'Angle', text: t })),
  ]

  return (
    <>
      <hr className="divider" />
      <div className="row wrap" style={{ gap: 22 }}>
        <div
          style={{
            textAlign: 'center',
            padding: '18px 26px',
            borderRadius: 'var(--r-lg)',
            background: passed ? 'var(--teal-tint)' : 'var(--amber-tint)',
          }}
        >
          <div
            className="display"
            style={{ fontWeight: 700, fontSize: 30, lineHeight: 1, color: passed ? 'var(--teal-ink)' : 'var(--amber-ink)' }}
          >
            {audit.score}
          </div>
          <div
            className="t-sm"
            style={{ marginTop: 6, fontWeight: 600, color: passed ? 'var(--teal-ink)' : 'var(--amber-ink)' }}
          >
            {audit.recommendation ?? (passed ? 'Pass' : 'Review')}
          </div>
        </div>
        <div style={{ flex: 1, minWidth: 240 }}>
          {audit.summary && (
            <p style={{ fontSize: 'var(--text-md)', lineHeight: 1.65, color: 'var(--ink-2)' }}>{audit.summary}</p>
          )}
          <div className="row wrap gap-8" style={{ marginTop: 12 }}>
            {audit.dedup_risk && <span className="chip chip--grey chip--wrap">dedup risk · {audit.dedup_risk}</span>}
            {audit.icp_fit && <span className="chip chip--grey chip--wrap">ICP fit · {audit.icp_fit}</span>}
          </div>
        </div>
      </div>

      {issues.length > 0 && (
        <ul className="stack gap-8" style={{ listStyle: 'none', marginTop: 18 }}>
          {issues.map((issue, i) => (
            <li key={i} className="notice notice--amber t-base">
              <strong style={{ flex: 'none' }}>{issue.kind}</strong>
              <span style={{ flex: 1, minWidth: 180 }}>{issue.text}</span>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

/* ── Draft ───────────────────────────────────────────────────────────────── */

export function DraftPanel({ post }: { post: BlogPost | null }) {
  const body = post?.mdx_final || post?.mdx_draft
  if (!body) {
    return <EmptyState title="No draft yet" hint="The writer agent fills this in once research clears the audit gate." />
  }

  return (
    <>
      <div className="row wrap gap-12 mb-18" style={{ justifyContent: 'space-between' }}>
        <p className="t-base muted">
          {num(post?.word_count ?? body.trim().split(/\s+/).length)} words · MDX
          {post?.mdx_final ? ' · final' : ' · unhumanised draft'}
        </p>
        <CopyButton text={body} label="MDX" className="btn btn--ghost btn--sm" />
      </div>
      {/*
        Rendered as text, never as HTML. This body is model-generated and is
        published to a live site — running it through `dangerouslySetInnerHTML`
        here would turn any prompt injection that reached the writer into stored
        XSS in the operator's own dashboard.
      */}
      <pre
        className="code scroller"
        style={{ maxHeight: 560, fontFamily: 'var(--font-sans)', fontSize: 'var(--text-md)', lineHeight: 1.8 }}
      >
        {body}
      </pre>
    </>
  )
}

/* ── Schema ──────────────────────────────────────────────────────────────── */

export function SchemaPanel({ schema }: { schema: unknown }) {
  if (!schema) {
    return <EmptyState title="No JSON-LD yet" hint="Generated at publish time as Article + FAQPage." />
  }
  const text = JSON.stringify(schema, null, 2)
  return (
    <>
      <div className="row wrap gap-12 mb-18" style={{ justifyContent: 'space-between' }}>
        <p className="t-base muted">JSON-LD · Article + FAQPage</p>
        <CopyButton text={text} label="JSON-LD" className="btn btn--ghost btn--sm" />
      </div>
      <pre className="code scroller" style={{ maxHeight: 560 }}>{text}</pre>
    </>
  )
}
