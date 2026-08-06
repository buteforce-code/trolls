'use client'

import { Fragment, useEffect, useMemo, useState, type ReactNode } from 'react'
import { fmtISTDate } from '../../lib/datetime'

// ── Types (mirror /api/performance) ────────────────────────────────────────
type Post = {
  slug: string; title: string; url: string | null
  publishedAt: string | null; ageDays: number | null
  tags: string[]; targetKeyword: string | null
  sourceKind: string | null; sourcePlatform: string | null; sourceUrl: string | null
  impressions: number; clicks: number; ctr: number | null; position: number | null
  views: number; users: number; engagementRate: number | null
  impressionsDelta: number | null; clicksDelta: number | null
}
type QueryRow = { query: string; impressions: number; clicks: number; position: number | null }
type Opportunity = Post & { fix: string }
type Drift = {
  slug: string; title: string; targetKeyword: string | null
  actualTopQuery: string; impressions: number; fix: string
}
type Report = {
  generatedAt: string; windowDays: number; hasData: boolean; lastIngestDate: string | null
  totals: {
    impressions: number; clicks: number; ctr: number | null; position: number | null; views: number
    impressionsDelta: number | null; clicksDelta: number | null; viewsDelta: number | null
  }
  series: { date: string; impressions: number; clicks: number }[]
  posts: Post[]
  topQueries: Record<string, QueryRow[]>
  opportunities: { pageTwo: Opportunity[]; lowCtr: Opportunity[]; intentDrift: Drift[] }
  bySource: { source: string; posts: number; impressions: number; clicks: number; impressionsPerPost: number }[]
  publishedCount: number
}

// ── formatting ─────────────────────────────────────────────────────────────
const pct = (v: number | null): string => (v === null ? '—' : `${(v * 100).toFixed(1)}%`)
const num = (v: number): string => v.toLocaleString()
const pos = (v: number | null): string => (v === null ? '—' : v.toFixed(1))

const SOURCE_COLOR: Record<string, string> = {
  linkedin: 'var(--blue)', reddit: 'var(--amber)', youtube: 'var(--red)',
  news: 'var(--accent)', web: 'var(--grey)', search_gap: 'var(--green)',
  own_analysis: 'var(--grey)',
}

function Delta({ value }: { value: number | null }) {
  if (value === null) return <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>new</span>
  const up = value >= 0
  return (
    <span style={{ color: up ? 'var(--green)' : 'var(--red)', fontSize: 12, fontWeight: 600 }}>
      {up ? '▲' : '▼'} {Math.abs(value).toFixed(0)}%
    </span>
  )
}

function SourceBadge({ kind, platform, url }: { kind: string | null; platform: string | null; url: string | null }) {
  if (!kind) return <span style={{ color: 'var(--text-dim)' }}>—</span>
  const label = platform && platform !== 'own_analysis' ? platform : kind
  const color = SOURCE_COLOR[platform || ''] || 'var(--grey)'
  const chip = (
    <span style={{
      fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999,
      border: `1px solid ${color}`, color, whiteSpace: 'nowrap',
    }}>{label}</span>
  )
  return url ? <a href={url} target="_blank" rel="noreferrer" title={url}>{chip}</a> : chip
}

function StatCard({ label, value, delta, hint }: {
  label: string; value: string; delta?: number | null; hint?: string
}) {
  return (
    <div className="card" style={{ padding: '16px 18px' }}>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 6 }}>
        <span style={{ fontSize: 30, fontWeight: 800, lineHeight: 1.1 }}>{value}</span>
        {delta !== undefined && <Delta value={delta} />}
      </div>
      {hint && <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>{hint}</div>}
    </div>
  )
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="card" style={{ padding: 20, marginBottom: 18 }}>
      <h2 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>{title}</h2>
      {subtitle && <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 12px' }}>{subtitle}</p>}
      {children}
    </div>
  )
}

/** Dual-axis daily chart. Impressions dwarf clicks by ~40x, so a shared axis
 *  would flatten the clicks line to the baseline and hide the thing that
 *  actually matters. */
function TrendChart({ series }: { series: { date: string; impressions: number; clicks: number }[] }) {
  const maxImp = Math.max(1, ...series.map(d => d.impressions))
  const maxClicks = Math.max(1, ...series.map(d => d.clicks))
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 140 }}>
        {series.map(d => (
          <div key={d.date} title={`${d.date}\n${d.impressions} impressions\n${d.clicks} clicks`}
               style={{ flex: 1, position: 'relative', height: '100%', display: 'flex', alignItems: 'flex-end' }}>
            <div style={{
              width: '100%', height: `${(d.impressions / maxImp) * 100}%`,
              minHeight: d.impressions > 0 ? 2 : 0,
              background: 'var(--accent)', opacity: d.impressions ? 0.45 : 0.1, borderRadius: 2,
            }} />
            {d.clicks > 0 && (
              <div style={{
                position: 'absolute', bottom: 0, width: '100%',
                height: `${(d.clicks / maxClicks) * 70}%`,
                borderTop: '2px solid var(--green)',
              }} />
            )}
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-dim)', marginTop: 6 }}>
        <span>{series[0]?.date}</span>
        <span>
          <span style={{ color: 'var(--accent)' }}>▬</span> impressions (max {maxImp}) &nbsp;
          <span style={{ color: 'var(--green)' }}>▬</span> clicks (max {maxClicks})
        </span>
        <span>{series[series.length - 1]?.date}</span>
      </div>
    </div>
  )
}

function OpportunityList({ items, empty }: { items: (Opportunity | Drift)[]; empty: string }) {
  if (!items.length) return <p style={{ fontSize: 13, color: 'var(--text-dim)', margin: 0 }}>{empty}</p>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {items.map(item => (
        <div key={item.slug} style={{
          padding: '10px 12px', background: 'var(--bg-hover)', borderRadius: 'var(--radius-sm)',
          borderLeft: '3px solid var(--amber)',
        }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{item.title}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 3 }}>{item.fix}</div>
          {'actualTopQuery' in item ? (
            <div style={{ fontSize: 12, marginTop: 5, fontFamily: 'var(--mono)' }}>
              targeted <span style={{ color: 'var(--text-dim)' }}>{item.targetKeyword}</span>
              {' → ranks for '}
              <span style={{ color: 'var(--amber)' }}>{item.actualTopQuery}</span>
              {` (${item.impressions} impr)`}
            </div>
          ) : (
            <div style={{ fontSize: 12, marginTop: 5, color: 'var(--text-dim)' }}>
              position {pos(item.position)} · {num(item.impressions)} impressions · CTR {pct(item.ctr)}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── page ───────────────────────────────────────────────────────────────────
export default function PerformancePage() {
  const [data, setData] = useState<Report | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/performance')
      .then(r => r.json())
      .then(d => (d.error ? setError(d.error) : setData(d)))
      .catch(e => setError(String(e)))
  }, [])

  const maxPerPost = useMemo(
    () => Math.max(1, ...(data?.bySource || []).map(s => s.impressionsPerPost)),
    [data],
  )

  if (error) {
    return <main className="container"><div className="card" style={{ padding: 20, color: 'var(--red)' }}>{error}</div></main>
  }
  if (!data) {
    return <main className="container"><div className="card" style={{ padding: 20 }}>Loading…</div></main>
  }

  const t = data.totals

  return (
    <main className="container" style={{ paddingBottom: 60 }}>
      <header style={{ margin: '24px 0 18px' }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>Performance</h1>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>
          What search and readers did with {data.publishedCount} published posts · last {data.windowDays} days
          {data.lastIngestDate && ` · data through ${fmtISTDate(data.lastIngestDate)} IST`}
        </p>
      </header>

      {!data.hasData && (
        <div className="card" style={{ padding: 18, marginBottom: 18, borderLeft: '3px solid var(--amber)' }}>
          <strong style={{ fontSize: 14 }}>No analytics ingested yet.</strong>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '6px 0 0' }}>
            Grant the service account read access in Search Console and GA4, then run{' '}
            <code>python run.py --check-analytics</code> to verify, and{' '}
            <code>python run.py --ingest-analytics --days 90</code> to backfill. Everything
            below fills in from that point.
          </p>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 12, marginBottom: 18 }}>
        <StatCard label="Impressions" value={num(t.impressions)} delta={t.impressionsDelta} hint="vs previous 28d" />
        <StatCard label="Clicks" value={num(t.clicks)} delta={t.clicksDelta} hint="vs previous 28d" />
        <StatCard label="CTR" value={pct(t.ctr)} hint="clicks ÷ impressions" />
        <StatCard label="Avg position" value={pos(t.position)} hint="impression-weighted" />
        <StatCard label="Pageviews" value={num(t.views)} delta={t.viewsDelta} hint="GA4" />
      </div>

      <Section title="Search trend" subtitle={`Daily impressions and clicks over ${data.windowDays} days`}>
        <TrendChart series={data.series} />
      </Section>

      <Section
        title="Where topics come from"
        subtitle="Average impressions per post, grouped by how the topic was sourced. This is the question the whole provenance layer exists to answer."
      >
        {data.bySource.length === 0 ? (
          <p style={{ fontSize: 13, color: 'var(--text-dim)', margin: 0 }}>No attributed posts with data yet.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.bySource.map(s => (
              <div key={s.source} style={{ display: 'grid', gridTemplateColumns: '180px 1fr 130px', gap: 12, alignItems: 'center' }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{s.source}</span>
                <div style={{ background: 'var(--bg-hover)', borderRadius: 4, height: 22, overflow: 'hidden' }}>
                  <div style={{
                    width: `${(s.impressionsPerPost / maxPerPost) * 100}%`, height: '100%',
                    background: 'var(--accent)', opacity: 0.7, borderRadius: 4,
                  }} />
                </div>
                <span style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'right' }}>
                  {num(s.impressionsPerPost)}/post · {s.posts} post{s.posts === 1 ? '' : 's'}
                </span>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="Fix these first" subtitle="Ranked by effort-to-impact, not by size">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 16 }}>
          <div>
            <h3 style={{ fontSize: 13, margin: '0 0 8px', color: 'var(--amber)' }}>Page 2, proven demand</h3>
            <OpportunityList items={data.opportunities.pageTwo} empty="Nothing sitting on page 2 with real impressions." />
          </div>
          <div>
            <h3 style={{ fontSize: 13, margin: '0 0 8px', color: 'var(--amber)' }}>Seen but not clicked</h3>
            <OpportunityList items={data.opportunities.lowCtr} empty="No page-1 posts with unusually low CTR." />
          </div>
          <div>
            <h3 style={{ fontSize: 13, margin: '0 0 8px', color: 'var(--amber)' }}>Intent drift</h3>
            <OpportunityList items={data.opportunities.intentDrift} empty="Every ranking post matches the keyword it targeted." />
          </div>
        </div>
      </Section>

      <Section title="Every post" subtitle="Click a row to see what it actually ranks for">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase' }}>
                <th style={{ padding: '6px 8px' }}>Post</th>
                <th style={{ padding: '6px 8px' }}>Source</th>
                <th style={{ padding: '6px 8px', textAlign: 'right' }}>Impr</th>
                <th style={{ padding: '6px 8px', textAlign: 'right' }}>Clicks</th>
                <th style={{ padding: '6px 8px', textAlign: 'right' }}>CTR</th>
                <th style={{ padding: '6px 8px', textAlign: 'right' }}>Pos</th>
                <th style={{ padding: '6px 8px', textAlign: 'right' }}>Age</th>
              </tr>
            </thead>
            <tbody>
              {data.posts.length === 0 && (
                <tr><td colSpan={7} style={{ padding: 16, color: 'var(--text-dim)' }}>No post has search data in this window yet.</td></tr>
              )}
              {data.posts.map(p => (
                <Fragment key={p.slug}>
                  <tr onClick={() => setExpanded(expanded === p.slug ? null : p.slug)}
                      style={{ borderTop: '1px solid var(--border)', cursor: 'pointer' }}>
                    <td style={{ padding: '8px' }}>
                      <div style={{ fontWeight: 600 }}>{p.title}</div>
                      {p.targetKeyword && (
                        <div style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>
                          target: {p.targetKeyword}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '8px' }}>
                      <SourceBadge kind={p.sourceKind} platform={p.sourcePlatform} url={p.sourceUrl} />
                    </td>
                    <td style={{ padding: '8px', textAlign: 'right' }}>
                      {num(p.impressions)} <Delta value={p.impressionsDelta} />
                    </td>
                    <td style={{ padding: '8px', textAlign: 'right' }}>{num(p.clicks)}</td>
                    <td style={{ padding: '8px', textAlign: 'right' }}>{pct(p.ctr)}</td>
                    <td style={{
                      padding: '8px', textAlign: 'right', fontWeight: 700,
                      color: p.position === null ? 'var(--text-dim)'
                        : p.position <= 10 ? 'var(--green)'
                        : p.position <= 20 ? 'var(--amber)' : 'var(--text-muted)',
                    }}>{pos(p.position)}</td>
                    <td style={{ padding: '8px', textAlign: 'right', color: 'var(--text-dim)' }}>
                      {p.ageDays === null ? '—' : `${p.ageDays}d`}
                    </td>
                  </tr>
                  {expanded === p.slug && (
                    <tr>
                      <td colSpan={7} style={{ padding: '4px 8px 14px', background: 'var(--bg-hover)' }}>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', margin: '8px 0 6px', textTransform: 'uppercase' }}>
                          Actually ranks for
                        </div>
                        {(data.topQueries[p.slug] || []).length === 0 ? (
                          <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
                            No query-level data — impressions were below Search Console&apos;s reporting threshold.
                          </span>
                        ) : (
                          <table style={{ width: '100%', fontSize: 12 }}>
                            <tbody>
                              {(data.topQueries[p.slug] || []).map(q => (
                                <tr key={q.query}>
                                  <td style={{ padding: '3px 0', fontFamily: 'var(--mono)' }}>{q.query}</td>
                                  <td style={{ textAlign: 'right', width: 90 }}>{num(q.impressions)} impr</td>
                                  <td style={{ textAlign: 'right', width: 70 }}>{q.clicks} clicks</td>
                                  <td style={{ textAlign: 'right', width: 70 }}>pos {pos(q.position)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </main>
  )
}
