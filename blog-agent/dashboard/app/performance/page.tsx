'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { delta, num, pct } from '../../lib/format'
import { PageHeader, EmptyState } from '../../components/ui/page-header'
import { SearchTrend, type TrendPoint } from '../../components/insights/search-trend'

interface PostRow {
  slug: string
  title: string
  url: string | null
  publishedAt: string | null
  ageDays: number | null
  targetKeyword: string | null
  sourceKind: string | null
  sourcePlatform: string | null
  impressions: number
  clicks: number
  ctr: number | null
  position: number | null
  views: number
  impressionsDelta: number | null
  clicksDelta: number | null
}

interface Opportunity {
  slug: string
  title: string
  fix: string
  impressions: number
  clicks: number
  ctr: number | null
  position: number | null
  targetKeyword?: string | null
  actualTopQuery?: string
}

interface PerformancePayload {
  generatedAt: string
  windowDays: number
  hasData: boolean
  lastIngestDate: string | null
  totals: {
    impressions: number; clicks: number; ctr: number | null; position: number | null; views: number
    impressionsDelta: number | null; clicksDelta: number | null; viewsDelta: number | null
  }
  series: TrendPoint[]
  posts: PostRow[]
  topQueries: Record<string, { query: string; impressions: number; clicks: number; position: number | null }[]>
  opportunities: { pageTwo: Opportunity[]; lowCtr: Opportunity[]; intentDrift: Opportunity[] }
  bySource: { source: string; posts: number; impressions: number; clicks: number; impressionsPerPost: number }[]
  publishedCount: number
}

export default function PerformancePage() {
  const [data, setData] = useState<PerformancePayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openRow, setOpenRow] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch('/api/performance', { headers: { accept: 'application/json' } })
      .then(async res => {
        if (res.status === 401) { window.location.reload(); return null }
        if (!res.ok) throw new Error(String(res.status))
        return res.json()
      })
      .then(payload => { if (payload && !cancelled) setData(payload as PerformancePayload) })
      .catch(err => { if (!cancelled) setError(err instanceof Error ? err.message : 'failed') })
    return () => { cancelled = true }
  }, [])

  if (error) {
    return (
      <>
        <PageHeader title="Performance" />
        <p className="notice notice--rose" role="alert">Could not build the report: {error}</p>
      </>
    )
  }

  if (!data) {
    return (
      <div aria-busy="true" aria-live="polite">
        <span className="sr-only">Building the performance report</span>
        <div className="grid-stats mb-22">
          {[0, 1, 2, 3, 4].map(i => <div key={i} className="card card--tight" style={{ height: 118 }} />)}
        </div>
        <div className="card" style={{ height: 320 }} />
      </div>
    )
  }

  if (!data.hasData) {
    return (
      <>
        <PageHeader
          title="Performance"
          subtitle="What search and readers did with the published posts."
        />
        <EmptyState
          title="No analytics ingested yet"
          hint={
            <>
              Search Console and GA4 rows land here after the first{' '}
              <code className="mono">python run.py --ingest-analytics</code> run. Until then this
              page has nothing true to show, so it shows nothing.
            </>
          }
        />
      </>
    )
  }

  const { totals } = data
  // Position is a rank: lower is better, so the arrow has to be inverted or the
  // card congratulates the site for sinking.
  const cards = [
    { label: 'Impressions', value: num(totals.impressions), d: delta(totals.impressionsDelta), hint: `vs previous ${data.windowDays}d` },
    { label: 'Clicks', value: num(totals.clicks), d: delta(totals.clicksDelta), hint: `vs previous ${data.windowDays}d` },
    { label: 'CTR', value: totals.ctr !== null ? pct(totals.ctr) : '—', d: null, hint: 'clicks / impressions' },
    { label: 'Avg position', value: totals.position !== null ? totals.position.toFixed(1) : '—', d: null, hint: 'impression-weighted' },
    { label: 'Pageviews', value: num(totals.views), d: delta(totals.viewsDelta), hint: 'GA4' },
  ]

  const sourceMax = Math.max(1, ...data.bySource.map(s => s.impressionsPerPost))

  return (
    <div className="view-enter">
      <PageHeader
        title="Performance"
        subtitle={`${data.publishedCount} published posts · last ${data.windowDays} days${data.lastIngestDate ? ` · data through ${data.lastIngestDate}` : ''}`}
      />

      <div className="grid-stats grid-stats--five mb-22">
        {cards.map((card, i) => (
          <section key={card.label} className="card card--tight rise spotlight" style={{ '--i': i } as React.CSSProperties}>
            <p className="t-sm muted" style={{ position: 'relative', zIndex: 1 }}>{card.label}</p>
            <p className="row gap-10" style={{ alignItems: 'baseline', margin: '8px 0 6px', position: 'relative', zIndex: 1 }}>
              <span className="stat-value stat-value--sm">{card.value}</span>
              {card.d && (
                <span className="t-sm" style={{ fontWeight: 600, color: card.d.tone }}>{card.d.text}</span>
              )}
            </p>
            <p className="t-xs faint" style={{ position: 'relative', zIndex: 1 }}>{card.hint}</p>
          </section>
        ))}
      </div>

      <SearchTrend series={data.series} />

      {data.bySource.length > 0 && (
        <section className="card rise mb-22" style={{ '--i': 6 } as React.CSSProperties}>
          <h2 className="section-title">Where topics come from</h2>
          <p className="section-note mb-18">
            Average impressions per post by how the topic was sourced. This is the question the
            whole provenance layer exists to answer.
          </p>
          <ul className="isolate stack gap-12" style={{ listStyle: 'none' }}>
            {data.bySource.map((source, i) => (
              <li
                key={source.source}
                className="isolate-item tip row gap-14"
                data-tip={`${source.source} → ${num(source.impressions)} impressions across ${source.posts} post${source.posts === 1 ? '' : 's'}`}
              >
                <span className="mono t-sm truncate" style={{ width: 140, flex: 'none', color: 'var(--ink-2)' }}>
                  {source.source}
                </span>
                <span className="track track--thick" style={{ flex: 1 }}>
                  <span
                    className="track-fill bar-grow-x"
                    style={{
                      display: 'block',
                      width: `${(source.impressionsPerPost / sourceMax) * 100}%`,
                      background: i === 0 ? 'var(--lav-deep)' : 'var(--lav)',
                      borderRadius: 'var(--r-xs)',
                      '--i': i,
                    } as React.CSSProperties}
                  />
                </span>
                <span className="t-sm tnum muted" style={{ width: 160, textAlign: 'right', flex: 'none' }}>
                  {num(source.impressionsPerPost)}/post · {source.posts} post{source.posts === 1 ? '' : 's'}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <FixTheseFirst opportunities={data.opportunities} />

      <section className="card rise" style={{ '--i': 8 } as React.CSSProperties}>
        <h2 className="section-title">Every post</h2>
        <p className="section-note mb-18">Open a row to see what it actually ranks for.</p>

        <div className="stack gap-10">
          {data.posts.map(post => {
            const open = openRow === post.slug
            const queries = data.topQueries[post.slug] ?? []
            const imprDelta = delta(post.impressionsDelta)
            const positionTone = post.position === null
              ? 'var(--ink-3)'
              : post.position <= 10 ? 'var(--teal-ink)' : post.position <= 20 ? 'var(--amber-ink)' : 'var(--ink-3)'

            return (
              <div key={post.slug} style={{ border: '1px solid var(--line)', borderRadius: 16 }}>
                <button
                  type="button"
                  className="row wrap gap-14"
                  aria-expanded={open}
                  aria-controls={`queries-${post.slug}`}
                  onClick={() => setOpenRow(open ? null : post.slug)}
                  style={{
                    width: '100%', textAlign: 'left', background: 'none', border: 0,
                    padding: '15px 17px', cursor: 'pointer', borderRadius: 16, font: 'inherit',
                  }}
                >
                  <span style={{ flex: 1, minWidth: 220 }}>
                    <span className="pretty" style={{ display: 'block', fontWeight: 600, fontSize: 'var(--text-md)', lineHeight: 1.4 }}>
                      {post.title}
                    </span>
                    <span className="mono t-xs" style={{ display: 'block', color: 'var(--ink-mute)', marginTop: 5 }}>
                      target: {post.targetKeyword || 'none set'}
                    </span>
                  </span>

                  {post.sourceKind && (
                    <span className="chip chip--grey" style={{ flex: 'none' }}>
                      {post.sourcePlatform || post.sourceKind}
                    </span>
                  )}

                  <span className="row" style={{ gap: 20, flex: 'none' }}>
                    <Metric width={78} value={num(post.impressions)} label={imprDelta.text} labelTone={imprDelta.tone} />
                    <Metric width={52} value={String(post.clicks)} label="clicks" />
                    <Metric width={52} value={post.ctr !== null ? pct(post.ctr) : '—'} label="CTR" />
                    <Metric width={52} value={post.position !== null ? post.position.toFixed(1) : '—'} label="pos" valueTone={positionTone} />
                    <Metric width={44} value={post.ageDays !== null ? `${post.ageDays}d` : '—'} label="age" />
                  </span>
                </button>

                {open && (
                  <div
                    id={`queries-${post.slug}`}
                    style={{ padding: '0 17px 15px', borderTop: '1px solid var(--line-hair)', marginTop: -1 }}
                  >
                    {queries.length === 0 ? (
                      <p className="t-sm muted" style={{ paddingTop: 14 }}>
                        No query-level data — impressions were below Search Console&apos;s reporting threshold.
                      </p>
                    ) : (
                      <>
                        <p className="t-xs" style={{ color: 'var(--ink-mute)', margin: '14px 0 9px', fontWeight: 500 }}>
                          Actually ranks for
                        </p>
                        <ul className="stack gap-8" style={{ listStyle: 'none' }}>
                          {queries.map(q => (
                            <li key={q.query} className="row gap-14" style={{ alignItems: 'baseline' }}>
                              <span className="mono t-sm truncate" style={{ flex: 1, color: 'var(--ink-2)' }}>{q.query}</span>
                              <span className="mono t-sm muted" style={{ width: 88, textAlign: 'right' }}>{num(q.impressions)} impr</span>
                              <span className="mono t-sm muted" style={{ width: 78, textAlign: 'right' }}>{q.clicks} clicks</span>
                              <span className="mono t-sm muted" style={{ width: 62, textAlign: 'right' }}>
                                {q.position !== null ? `pos ${q.position}` : '—'}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                    <Link href={`/topic/${post.slug}`} className="btn btn--ghost btn--xs" style={{ marginTop: 14 }}>
                      Open the topic
                    </Link>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>
    </div>
  )
}

function Metric({ width, value, label, valueTone, labelTone }: {
  width: number; value: string; label: string; valueTone?: string; labelTone?: string
}) {
  return (
    <span className="tnum" style={{ width, textAlign: 'right', display: 'block' }}>
      <span style={{ display: 'block', fontSize: 'var(--text-base)', fontWeight: 600, color: valueTone }}>{value}</span>
      <span style={{ display: 'block', fontSize: 11, marginTop: 3, color: labelTone ?? 'var(--ink-faint)' }}>{label}</span>
    </span>
  )
}

function FixTheseFirst({ opportunities }: { opportunities: PerformancePayload['opportunities'] }) {
  const columns = [
    { title: 'Page 2, proven demand', items: opportunities.pageTwo },
    { title: 'Seen but not clicked', items: opportunities.lowCtr },
    { title: 'Intent drift', items: opportunities.intentDrift },
  ]
  if (columns.every(c => c.items.length === 0)) return null

  return (
    <section className="card rise mb-22" style={{ '--i': 7 } as React.CSSProperties}>
      <h2 className="section-title">Fix these first</h2>
      <p className="section-note mb-18">Ranked by effort-to-impact, not by size.</p>
      <div className="grid-cards" style={{ gap: 20 }}>
        {columns.map(column => (
          <div key={column.title}>
            <h3 className="t-base" style={{ fontWeight: 600, color: 'var(--amber-ink)', marginBottom: 11 }}>
              {column.title}
            </h3>
            {column.items.length === 0 ? (
              <p className="t-sm muted">Nothing in this bucket right now.</p>
            ) : (
              <ul className="stack gap-10" style={{ listStyle: 'none' }}>
                {column.items.slice(0, 3).map(item => (
                  <li key={item.slug} style={{ background: 'var(--amber-tint)', borderRadius: 14, padding: '14px 15px' }}>
                    <Link href={`/topic/${item.slug}`} className="pretty" style={{ fontWeight: 600, fontSize: 'var(--text-base)', lineHeight: 1.45, color: 'var(--ink)' }}>
                      {item.title}
                    </Link>
                    <p className="t-sm" style={{ color: 'var(--amber-ink)', marginTop: 6, lineHeight: 1.55 }}>{item.fix}</p>
                    <p className="mono t-xs" style={{ color: 'var(--amber-ink)', marginTop: 8 }}>
                      {item.actualTopQuery
                        ? <>targeted {item.targetKeyword} → ranks for {item.actualTopQuery} ({num(item.impressions)} impr)</>
                        : <>position {item.position?.toFixed(1) ?? '—'} · {num(item.impressions)} impressions · CTR {item.ctr !== null ? pct(item.ctr) : '—'}</>}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}
