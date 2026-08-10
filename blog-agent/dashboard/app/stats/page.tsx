'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { clockTime, num, relative, untilShort } from '../../lib/format'
import { PageHeader, EmptyState } from '../../components/ui/page-header'
import { CadenceChart, CadenceLegend, type CadenceDay } from '../../components/ui/cadence-chart'

interface StatsPayload {
  generatedAt: string
  totals: {
    topics: number; published: number; scheduled: number; queued: number
    needsReview: number; failed: number; inProgress: number
  }
  content: {
    posts: number; totalWords: number; avgWords: number | null; medianWords: number | null
    withHeroImage: number; withSchema: number; withSocial: number
    audited: number; avgAuditScore: number | null; avgConfidence: number | null
  }
  cadence: {
    publishedByDay: CadenceDay[]
    upcoming: { slug: string; title: string; scheduled_for: string }[]
    lastPublishedAt: string | null
    nextPublishAt: string | null
  }
  views: {
    total: number; last7: number; last30: number; uniquePosts: number
    byDay: CadenceDay[]
    topPosts: { slug: string; title: string; views: number; published_url: string | null }[]
    tracking: boolean
  }
  tags: { tag: string; count: number }[]
}

export default function StatsPage() {
  const [data, setData] = useState<StatsPayload | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Deliberately a one-shot read with no polling. Nothing on this page changes
  // faster than a post is published, and it is the most expensive query in the
  // app — it reads every topic, post and view row.
  useEffect(() => {
    let cancelled = false
    fetch('/api/stats', { headers: { accept: 'application/json' } })
      .then(async res => {
        if (res.status === 401) { window.location.reload(); return null }
        if (!res.ok) throw new Error(String(res.status))
        return res.json()
      })
      .then(payload => { if (payload && !cancelled) setData(payload as StatsPayload) })
      .catch(err => { if (!cancelled) setError(err instanceof Error ? err.message : 'failed') })
    return () => { cancelled = true }
  }, [])

  if (error) {
    return (
      <>
        <PageHeader title="Analytics" ambient={false} />
        <p className="notice notice--rose" role="alert">Could not build the report: {error}</p>
      </>
    )
  }

  if (!data) {
    return (
      <div aria-busy="true" aria-live="polite">
        <span className="sr-only">Building the report</span>
        <div className="grid-stats mb-22">
          {[0, 1, 2, 3].map(i => <div key={i} className="card card--tight" style={{ height: 120 }} />)}
        </div>
        <div className="card" style={{ height: 300 }} />
      </div>
    )
  }

  const { totals, content, cadence, views, tags } = data
  const pct = (n: number) => (content.posts ? `${Math.round((n / content.posts) * 100)}%` : '—')

  const quality: [string, string | number][] = [
    ['Published posts', content.posts],
    ['Total words', num(content.totalWords)],
    ['Average word count', content.avgWords !== null ? num(Math.round(content.avgWords)) : '—'],
    ['Median word count', content.medianWords !== null ? num(content.medianWords) : '—'],
    ['With schema', pct(content.withSchema)],
    ['With a social kit', pct(content.withSocial)],
    ['With a hero image', pct(content.withHeroImage)],
    ['Average audit score', content.avgAuditScore !== null ? `${content.avgAuditScore.toFixed(1)} / 100` : 'not scored yet'],
    // The research agent has emitted confidence on both a 0–1 and a 0–100 scale
    // across the corpus's lifetime. Rendering the raw number either way reads as
    // a bug, so the scale is inferred and stated.
    ['Average research confidence', content.avgConfidence === null
      ? 'not recorded'
      : content.avgConfidence <= 1
        ? content.avgConfidence.toFixed(2)
        : `${content.avgConfidence.toFixed(1)} / 100`],
  ]

  const totalCards: { label: string; value: number; tone: string }[] = [
    { label: 'topics in play', value: totals.topics,      tone: 'var(--ink)' },
    { label: 'published',      value: totals.published,   tone: 'var(--teal-ink)' },
    { label: 'scheduled',      value: totals.scheduled,   tone: 'var(--lav-ink)' },
    { label: 'needs review',   value: totals.needsReview + totals.failed, tone: 'var(--rose-ink)' },
  ]

  const tagMax = Math.max(1, ...tags.map(t => t.count))

  return (
    <div className="view-enter">
      <PageHeader
        title="Analytics"
        subtitle={`Read-only · generated ${clockTime(data.generatedAt)}`}
        ambient={false}
      />

      <div className="grid-stats mb-22">
        {totalCards.map((card, i) => (
          <div key={card.label} className="card card--tight rise" style={{ '--i': i } as React.CSSProperties}>
            <p className="stat-value" style={{ fontSize: 34, color: card.tone }}>{card.value}</p>
            <p className="t-base muted" style={{ marginTop: 11 }}>{card.label}</p>
          </div>
        ))}
      </div>

      <section className="card rise mb-22" style={{ '--i': 4 } as React.CSSProperties}>
        <div className="row wrap gap-18" style={{ justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <h2 className="section-title">Publishing cadence</h2>
            <p className="section-note">
              Last published {cadence.lastPublishedAt ? relative(cadence.lastPublishedAt) : '—'} ·
              next {cadence.nextPublishAt ? untilShort(cadence.nextPublishAt) : '—'}
            </p>
          </div>
          <CadenceLegend />
        </div>
        <CadenceChart days={cadence.publishedByDay} height={154} />
      </section>

      <div className="grid-halves mb-22">
        <section className="card rise" style={{ '--i': 5 } as React.CSSProperties}>
          <h2 className="section-title mb-18">Content quality</h2>
          <dl>
            {quality.map(([label, value]) => (
              <div
                key={label}
                className="row"
                style={{
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  padding: '11px 0',
                  borderBottom: '1px solid var(--line-hair)',
                }}
              >
                <dt className="t-base muted">{label}</dt>
                <dd className="display" style={{ fontWeight: 600, fontSize: 15 }}>{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="card rise" style={{ '--i': 6 } as React.CSSProperties}>
          <h2 className="section-title mb-18">Blog views</h2>
          {!views.tracking || views.total === 0 ? (
            <div
              style={{
                background: 'var(--surface-sunk)',
                border: '1px dashed var(--line-strong)',
                borderRadius: 'var(--r-lg)',
                padding: 24,
              }}
            >
              <div className="row gap-10" style={{ marginBottom: 11 }}>
                <span className="dot dot--lg" style={{ background: 'var(--ink-faint)', color: 'var(--ink-faint)' }} aria-hidden="true" />
                <span className="display" style={{ fontWeight: 600, fontSize: 15 }}>
                  Tracking is not wired up yet
                </span>
              </div>
              <p className="t-base muted" style={{ lineHeight: 1.65, marginBottom: 18 }}>
                The <code className="mono" style={{ color: 'var(--lav-ink)', background: 'var(--lav-tint)', padding: '2px 6px', borderRadius: 6 }}>/api/track</code>{' '}
                snippet is not on the live site, so views read zero. Add it to the post template and
                this fills in — the number is not being hidden, it is not being collected.
              </p>
              <div className="row" style={{ gap: 30 }}>
                <div>
                  <div className="display" style={{ fontWeight: 700, fontSize: 26, color: '#C9C6D8' }}>0</div>
                  <div className="t-sm muted" style={{ marginTop: 3 }}>total views</div>
                </div>
                <div>
                  <div className="display" style={{ fontWeight: 700, fontSize: 26, color: '#C9C6D8' }}>0</div>
                  <div className="t-sm muted" style={{ marginTop: 3 }}>last 7 days</div>
                </div>
              </div>
            </div>
          ) : (
            <>
              <div className="row wrap" style={{ gap: 30, marginBottom: 20 }}>
                <div>
                  <div className="stat-value stat-value--sm">{num(views.total)}</div>
                  <div className="t-sm muted" style={{ marginTop: 4 }}>total views</div>
                </div>
                <div>
                  <div className="stat-value stat-value--sm">{num(views.last7)}</div>
                  <div className="t-sm muted" style={{ marginTop: 4 }}>last 7 days</div>
                </div>
                <div>
                  <div className="stat-value stat-value--sm">{views.uniquePosts}</div>
                  <div className="t-sm muted" style={{ marginTop: 4 }}>posts with views</div>
                </div>
              </div>
              <ul className="stack gap-8" style={{ listStyle: 'none' }}>
                {views.topPosts.slice(0, 6).map(post => (
                  <li key={post.slug} className="row gap-12 hover-row" style={{ padding: '8px 10px' }}>
                    <Link href={`/topic/${post.slug}`} className="truncate t-base" style={{ flex: 1, color: 'var(--ink-2)' }}>
                      {post.title}
                    </Link>
                    <span className="mono t-sm muted">{num(post.views)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>

      <div className="grid-halves">
        <section className="card rise" style={{ '--i': 7 } as React.CSSProperties}>
          <h2 className="section-title" style={{ marginBottom: 14 }}>Upcoming schedule</h2>
          {cadence.upcoming.length === 0 ? (
            <EmptyState title="Nothing scheduled" hint="Approved drafts land here with an auto-publish time." />
          ) : (
            <div className="x-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Title</th>
                    <th scope="col" style={{ textAlign: 'right' }}>Auto-publishes</th>
                  </tr>
                </thead>
                <tbody>
                  {cadence.upcoming.map(item => (
                    <tr key={item.slug}>
                      <td>
                        <Link href={`/topic/${item.slug}`} style={{ fontWeight: 500, color: 'var(--ink)' }}>
                          {item.title}
                        </Link>
                      </td>
                      <td
                        className="tnum"
                        style={{ textAlign: 'right', color: 'var(--lav-ink)', fontWeight: 600 }}
                      >
                        {untilShort(item.scheduled_for)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="card rise" style={{ '--i': 8 } as React.CSSProperties}>
          <h2 className="section-title mb-18">Top tags</h2>
          {tags.length === 0 ? (
            <EmptyState title="No tags yet" hint="Tags come from the brief and drive the blog taxonomy." />
          ) : (
            <ul className="stack gap-12" style={{ listStyle: 'none' }}>
              {tags.map((tag, i) => (
                <li key={tag.tag} className="row gap-12">
                  <span className="truncate t-base" style={{ width: 148, flex: 'none', color: 'var(--ink-2)' }}>
                    {tag.tag}
                  </span>
                  <span className="track track--thin" style={{ flex: 1 }}>
                    <span
                      className="track-fill bar-grow-x"
                      style={{
                        display: 'block',
                        width: `${(tag.count / tagMax) * 100}%`,
                        background: i === 0 ? 'var(--lav-deep)' : 'var(--lav)',
                        '--i': i,
                      } as React.CSSProperties}
                    />
                  </span>
                  <span className="t-base tnum muted" style={{ width: 22, textAlign: 'right' }}>{tag.count}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}
