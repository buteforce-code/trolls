'use client'

import { useEffect, useState, type ReactNode } from 'react'
import Link from 'next/link'

// ── Types (mirror /api/stats) ──────────────────────────────────────────────
type Day = { date: string; count: number }
type Stats = {
  generatedAt: string
  totals: { topics: number; published: number; scheduled: number; queued: number; needsReview: number; failed: number; inProgress: number }
  statusCounts: Record<string, number>
  content: {
    posts: number; totalWords: number; avgWords: number | null; medianWords: number | null
    withHeroImage: number; withSchema: number; withSocial: number
    audited: number; avgAuditScore: number | null; avgConfidence: number | null
  }
  cadence: { publishedByDay: Day[]; upcoming: { slug: string; title: string; scheduled_for: string }[]; lastPublishedAt: string | null; nextPublishAt: string | null }
  views: { total: number; last7: number; last30: number; uniquePosts: number; byDay: Day[]; topPosts: { slug: string; title: string; views: number; published_url: string | null }[]; tracking: boolean }
  tags: { tag: string; count: number }[]
}

const STATUS_LABEL: Record<string, string> = {
  queued: 'Queued', researching: 'Researching', verifying_research: 'Review research',
  writing: 'Writing', verifying_draft: 'Review draft', scheduled: 'Scheduled',
  publishing: 'Publishing', published: 'Published', cancelled: 'Cancelled', failed: 'Failed',
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
function until(iso: string): string {
  const diff = new Date(iso).getTime() - Date.now()
  if (diff <= 0) return 'now'
  const h = Math.round(diff / 3.6e6)
  return h < 48 ? `in ${h}h` : `in ${Math.round(h / 24)}d`
}

// ── Presentational bits ─────────────────────────────────────────────────────
function StatCard({ label, value, accent, hint }: { label: string; value: string | number; accent?: string; hint?: string }) {
  return (
    <div className="card" style={{ padding: '16px 18px' }}>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</div>
      <div style={{ fontSize: 30, fontWeight: 800, lineHeight: 1.1, marginTop: 6, color: accent || 'var(--text)' }}>{value}</div>
      {hint && <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>{hint}</div>}
    </div>
  )
}

function BarChart({ data, color = 'var(--accent)', unit = '' }: { data: Day[]; color?: string; unit?: string }) {
  const max = Math.max(1, ...data.map(d => d.count))
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 120, marginTop: 8 }}>
      {data.map(d => (
        <div key={d.date} title={`${d.date}: ${d.count}${unit}`} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%' }}>
          <div style={{
            height: `${(d.count / max) * 100}%`, minHeight: d.count > 0 ? 3 : 0,
            background: color, borderRadius: 3, opacity: d.count > 0 ? 1 : 0.15,
            transition: 'height .2s',
          }} />
        </div>
      ))}
    </div>
  )
}

function Section({ title, children, right }: { title: string; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="card" style={{ padding: 20, marginBottom: 18 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
        <h2 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>{title}</h2>
        {right && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{right}</span>}
      </div>
      {children}
    </div>
  )
}

function Meter({ label, value, total }: { label: string; value: number; total: number }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 4 }}>
        <span>{label}</span>
        <span style={{ color: 'var(--text-muted)' }}>{value}/{total} · {pct}%</span>
      </div>
      <div style={{ height: 7, background: 'var(--bg-input)', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: 'var(--accent)' }} />
      </div>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function StatsPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const load = () => fetch('/api/stats')
      .then(r => r.json())
      .then(d => { if (!cancelled) { d.error ? setError(d.error) : setStats(d) } })
      .catch(e => !cancelled && setError(String(e)))
    load()
    const t = setInterval(load, 30000)
    return () => { cancelled = true; clearInterval(t) }
  }, [])

  return (
    <main>
      <div className="container">
        <div className="page-header">
          <div className="page-header-row">
            <div>
              <h1>Analytics</h1>
              <p>Pipeline, content &amp; traffic{stats && <> · updated {fmtDate(stats.generatedAt)}</>}</p>
            </div>
            <Link href="/" className="btn btn-outline">← Topics</Link>
          </div>
        </div>

        {error && <div className="card" style={{ padding: 16, color: 'var(--red)' }}>Failed to load stats: {error}</div>}
        {!stats && !error && <div className="empty"><div className="empty-icon">⏳</div><h2>Loading analytics…</h2></div>}

        {stats && (
          <>
            {/* KPI row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 14, marginBottom: 18 }}>
              <StatCard label="Total views" value={stats.views.total.toLocaleString()} accent="var(--accent)" hint={`${stats.views.last7} last 7d · ${stats.views.last30} last 30d`} />
              <StatCard label="Published" value={stats.totals.published} accent="var(--green)" hint={`${stats.views.uniquePosts} posts with views`} />
              <StatCard label="Scheduled" value={stats.totals.scheduled} accent="var(--accent)" hint={stats.cadence.nextPublishAt ? `next ${until(stats.cadence.nextPublishAt)}` : 'none queued'} />
              <StatCard label="Queued" value={stats.totals.queued} hint="awaiting pipeline" />
              <StatCard label="Needs review" value={stats.totals.needsReview} accent={stats.totals.needsReview ? 'var(--amber)' : undefined} />
              <StatCard label="Failed" value={stats.totals.failed} accent={stats.totals.failed ? 'var(--red)' : undefined} />
            </div>

            {/* Views over time */}
            <Section title="Blog views — last 30 days" right={stats.views.tracking ? `${stats.views.total.toLocaleString()} total` : 'tracking not active yet'}>
              {stats.views.total === 0 ? (
                <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0 }}>
                  No views recorded yet. Add the tracking snippet (see README “View tracking”) to the published blog template — counts appear here automatically.
                </p>
              ) : <BarChart data={stats.views.byDay} color="var(--accent)" />}
            </Section>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 18 }}>
              {/* Publishing cadence */}
              <Section title="Publishing cadence — last 30 days" right={stats.cadence.lastPublishedAt ? `last ${fmtDate(stats.cadence.lastPublishedAt)}` : 'none yet'}>
                <BarChart data={stats.cadence.publishedByDay} color="var(--green)" />
              </Section>

              {/* Pipeline breakdown */}
              <Section title="Pipeline status">
                {Object.entries(stats.statusCounts).sort((a, b) => b[1] - a[1]).map(([s, n]) => (
                  <div key={s} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '5px 0' }}>
                    <span className={`badge badge-${s}`}>{STATUS_LABEL[s] ?? s}</span>
                    <strong style={{ fontSize: 14 }}>{n}</strong>
                  </div>
                ))}
              </Section>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 18 }}>
              {/* Top posts */}
              <Section title="Top posts by views">
                {stats.views.topPosts.length === 0 ? (
                  <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0 }}>No view data yet.</p>
                ) : stats.views.topPosts.map((p, i) => (
                  <div key={p.slug} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                    <span style={{ width: 20, color: 'var(--text-dim)', fontFamily: 'var(--mono)', fontSize: 12 }}>{i + 1}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.title}</div>
                      <Link href={`/topic/${p.slug}`} style={{ fontSize: 11, color: 'var(--text-muted)' }}>/{p.slug}</Link>
                    </div>
                    <strong style={{ color: 'var(--accent)' }}>{p.views.toLocaleString()}</strong>
                  </div>
                ))}
              </Section>

              {/* Content quality */}
              <Section title="Content quality" right={`${stats.content.posts} posts`}>
                <div style={{ display: 'flex', gap: 18, marginBottom: 14, flexWrap: 'wrap' }}>
                  <div><div style={{ fontSize: 22, fontWeight: 800 }}>{stats.content.avgWords ?? '—'}</div><div style={{ fontSize: 11, color: 'var(--text-muted)' }}>avg words</div></div>
                  <div><div style={{ fontSize: 22, fontWeight: 800 }}>{stats.content.avgAuditScore ?? '—'}</div><div style={{ fontSize: 11, color: 'var(--text-muted)' }}>avg audit score</div></div>
                  <div><div style={{ fontSize: 22, fontWeight: 800 }}>{stats.content.avgConfidence ?? '—'}</div><div style={{ fontSize: 11, color: 'var(--text-muted)' }}>avg research conf.</div></div>
                </div>
                <Meter label="Hero image" value={stats.content.withHeroImage} total={stats.content.posts} />
                <Meter label="JSON-LD schema" value={stats.content.withSchema} total={stats.content.posts} />
                <Meter label="Social kit" value={stats.content.withSocial} total={stats.content.posts} />
                <Meter label="Audited" value={stats.content.audited} total={stats.content.posts} />
              </Section>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 18 }}>
              {/* Upcoming schedule */}
              <Section title="Upcoming auto-publishes" right={`${stats.cadence.upcoming.length} scheduled`}>
                {stats.cadence.upcoming.length === 0 ? (
                  <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0 }}>Nothing scheduled.</p>
                ) : stats.cadence.upcoming.slice(0, 12).map(u => (
                  <div key={u.slug} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                    <Link href={`/topic/${u.slug}`} style={{ fontSize: 13, flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{u.title}</Link>
                    <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>{until(u.scheduled_for)}</span>
                  </div>
                ))}
              </Section>

              {/* Tags */}
              <Section title="Top tags">
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {stats.tags.map(t => (
                    <span key={t.tag} className="tag">{t.tag} · {t.count}</span>
                  ))}
                </div>
              </Section>
            </div>
          </>
        )}
      </div>
    </main>
  )
}
