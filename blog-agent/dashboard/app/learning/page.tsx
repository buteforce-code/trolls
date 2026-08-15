'use client'

import Link from 'next/link'
import { num, relative } from '../../lib/format'
import { usePoll } from '../../lib/use-poll'
import { PageHeader, EmptyState } from '../../components/ui/page-header'
import { PosteriorChart, type Arm } from '../../components/insights/posterior-chart'
import { CalibrationChart, type CalibrationBucket } from '../../components/insights/calibration-chart'
import { HistoryChart, type Snapshot } from '../../components/insights/history-chart'

interface PostScore {
  slug: string
  title: string
  matured: boolean | null
  age_days: number | null
  outcome_score: number | string | null
  components: Record<string, number> | null
}

interface Decision {
  slug: string
  title: string
  arm: string | null
  mode: string | null
  rank: number | null
  sampled: number | string | null
}

interface Signal {
  title: string
  platform: string | null
  source: string
  cluster: string | null
  score: number | null
  reject_reason: string | null
}

interface LearningPayload {
  generatedAt: string
  hasRun: boolean
  status: {
    mode: string
    bandiActive: boolean
    matured: number
    threshold: number
    scored: number
    armCount: number
    globalRate: number | null
    lastRunAt: string | null
    reason: string
  }
  arms: Arm[]
  posts: PostScore[]
  ranking: Decision[]
  /** One row per `--learn` run, oldest first. The engine's own history. */
  snapshots: Snapshot[]
  calibration: { buckets: CalibrationBucket[]; brier: number | null; n: number }
  formats: { format: string; total: number; published: number }[]
  scout: {
    accepted: Signal[]
    rejected: Signal[]
    lastSweep: string | null
    bySource: { source: string; count: number }[]
  }
}

const COMPONENT_COLOURS: Record<string, string> = {
  impressions: 'var(--lav-deep)',
  clicks: 'var(--teal)',
  position: 'var(--lav-ink)',
  ctr: 'var(--amber)',
  engagement: 'var(--rose)',
}

/**
 * The learning report refreshes on a slow poll rather than once on mount.
 *
 * `--learn` runs nightly after the analytics ingest, so there is no fast-moving
 * state here and a 3s poll would be pure waste. A minute is enough that a tab
 * left open overnight shows this morning's run instead of yesterday's, which is
 * the actual failure a one-shot fetch produced.
 */
const REFRESH_MS = 60_000

export default function LearningPage() {
  const { data, error } = usePoll<LearningPayload>(
    '/api/learning',
    () => false,
    { activeMs: REFRESH_MS, idleMs: REFRESH_MS },
  )

  if (error) {
    return (
      <>
        <PageHeader title="Learning" />
        <p className="notice notice--rose" role="alert">Could not build the report: {error}</p>
      </>
    )
  }

  if (!data) {
    return (
      <div aria-busy="true" aria-live="polite">
        <span className="sr-only">Reading what the engine believes</span>
        <div className="card mb-22" style={{ height: 140 }} />
        <div className="card" style={{ height: 380 }} />
      </div>
    )
  }

  if (!data.hasRun) {
    return (
      <>
        <PageHeader
          title="Learning"
          subtitle="What the engine believes about its own content, and how it decides what to write next."
        />
        <EmptyState
          title="The learning run has never executed"
          hint={
            <>
              Every number on this page is computed by{' '}
              <code className="mono">python run.py --learn</code> and stored — the dashboard never
              recomputes a score, so that the formula ranking the production queue and the formula
              behind these charts can never drift apart. Until that runs, there is nothing to show.
            </>
          }
        />
      </>
    )
  }

  const { status, arms, posts, ranking, calibration, formats, scout } = data
  const snapshots = data.snapshots ?? []
  const toMaturity = Math.max(0, status.threshold - status.matured)
  const scoreMax = Math.max(1, ...posts.map(p => Number(p.outcome_score ?? 0)))
  const formatMax = Math.max(1, ...formats.map(f => f.total))
  const publishedTotal = formats.reduce((a, f) => a + f.published, 0)
  const topFormat = formats.slice().sort((a, b) => b.published - a.published)[0]

  return (
    <div className="view-enter">
      <PageHeader
        title="Learning"
        subtitle={`What the engine believes about its own content, and how it decides what to write next${status.lastRunAt ? ` · last run ${relative(status.lastRunAt)}` : ''}`}
      />

      <section className="card card--tight rise mb-22" style={{ '--i': 0 } as React.CSSProperties}>
        <div className="row wrap gap-12">
          <span className={`chip ${status.mode === 'active' ? 'chip--teal' : 'chip--amber'}`} style={{ textTransform: 'uppercase', letterSpacing: '.06em', fontSize: 'var(--text-xs)', fontWeight: 700 }}>
            {status.mode === 'active' ? 'Steering the queue' : 'Shadow mode'}
          </span>
          <span className="t-base" style={{ color: 'var(--ink-2)', flex: 1, minWidth: 260 }}>
            {status.reason}
          </span>
        </div>

        <div className="row wrap" style={{ gap: 30, marginTop: 18 }}>
          {[
            { n: num(status.scored), label: 'posts scored' },
            { n: `${status.matured}`, label: `matured (of ${status.threshold} needed)` },
            { n: `${status.armCount}`, label: 'arms' },
            { n: status.globalRate !== null ? `${Math.round(status.globalRate * 100)}%` : '—', label: 'site-wide success rate' },
          ].map(stat => (
            <div key={stat.label}>
              <div className="display tnum" style={{ fontWeight: 700, fontSize: 24, letterSpacing: '-.03em' }}>{stat.n}</div>
              <div className="t-sm muted" style={{ marginTop: 4 }}>{stat.label}</div>
            </div>
          ))}
        </div>

        {status.mode !== 'active' && (
          <p className="t-sm" style={{ marginTop: 16, lineHeight: 1.6, color: 'var(--ink-3)' }}>
            The engine is recording what it would choose. Everything below is a live belief — it is
            just not being acted on yet.{' '}
            {toMaturity > 0
              ? `${toMaturity} more matured post${toMaturity === 1 ? '' : 's'} before it may steer.`
              : status.bandiActive
                ? ''
                : 'It has the data it needs — steering is held by the LEARN_BANDIT_ACTIVE flag, '
                  + 'which is a decision, not a fault.'}
          </p>
        )}
      </section>

      {snapshots.length > 0 && (
        <section className="card rise mb-22" style={{ '--i': 1 } as React.CSSProperties}>
          <div className="row wrap gap-18" style={{ justifyContent: 'space-between', marginBottom: 6 }}>
            <div>
              <h2 className="section-title">How the belief has moved</h2>
              <p className="section-note">
                One point per learning run. This is the only chart here that shows change over
                time — everything else is what the engine believes right now.
              </p>
            </div>
          </div>
          <HistoryChart snapshots={snapshots} threshold={status.threshold} />
        </section>
      )}

      {arms.length > 0 && (
        <section className="card rise mb-22" style={{ '--i': 2 } as React.CSSProperties}>
          <h2 className="section-title">What the engine believes</h2>
          <p className="section-note mb-18">
            One curve per arm — a content cluster paired with where its topics came from. A tall
            narrow curve means confident; a low wide one means it is still guessing and will keep
            exploring. Every arm starts at the site-wide average, which is what stops one viral post
            capturing the system.
          </p>
          <PosteriorChart arms={arms} />
        </section>
      )}

      <div className="grid-halves mb-22">
        <section className="card rise" style={{ '--i': 2 } as React.CSSProperties}>
          <h2 className="section-title">What it would write next</h2>
          <p className="section-note mb-18">
            Queued topics ranked by Thompson sampling. “Explore” means uncertainty drove the pick
            rather than evidence — the mechanism working, not a mistake.
          </p>
          {ranking.length === 0 ? (
            <p className="t-base muted">No ranking recorded on the last run.</p>
          ) : (
            <ol className="stack gap-10" style={{ listStyle: 'none' }}>
              {ranking.map((row, i) => (
                <li
                  key={row.slug}
                  className="row gap-14"
                  style={{
                    padding: '11px 13px',
                    borderRadius: 14,
                    background: i === 0 ? 'var(--surface-sunk)' : 'transparent',
                    border: `1px solid ${i === 0 ? 'var(--line)' : 'transparent'}`,
                  }}
                >
                  <span className="display" style={{ fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--ink-faint)', width: 14, flex: 'none' }}>
                    {row.rank ?? i + 1}
                  </span>
                  <span style={{ minWidth: 0, flex: 1 }}>
                    <Link href={`/topic/${row.slug}`} className="pretty" style={{ display: 'block', fontSize: 'var(--text-base)', fontWeight: 600, lineHeight: 1.4, color: 'var(--ink)' }}>
                      {row.title}
                    </Link>
                    <span className="mono t-xs" style={{ display: 'block', color: 'var(--ink-mute)', marginTop: 4 }}>
                      {row.arm ?? 'unassigned arm'}
                    </span>
                  </span>
                  {row.mode && (
                    <span className={`chip ${row.mode === 'explore' ? 'chip--lav' : 'chip--teal'}`} style={{ flex: 'none' }}>
                      {row.mode}
                    </span>
                  )}
                  <span className="mono t-sm muted" style={{ flex: 'none', width: 74, textAlign: 'right' }}>
                    {row.sampled !== null ? `draw ${Math.round(Number(row.sampled) * 100)}%` : '—'}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className="card rise" style={{ '--i': 3 } as React.CSSProperties}>
          <h2 className="section-title">Is it right?</h2>
          <p className="section-note mb-18">
            Calibration: when the engine says an arm succeeds 60% of the time, does it? This is the
            check that decides whether the beliefs are worth acting on.
          </p>
          <CalibrationChart
            buckets={calibration.buckets}
            brier={calibration.brier}
            n={calibration.n}
          />
        </section>
      </div>

      {posts.length > 0 && (
        <section className="card rise mb-22" style={{ '--i': 4 } as React.CSSProperties}>
          <h2 className="section-title">Why each post scored what it did</h2>
          <p className="section-note mb-18">
            The deterministic layer, term by term. Impressions and clicks enter through a log curve
            so one outlier cannot dominate; posts younger than the maturity window are carried but
            not judged.
          </p>
          <ul className="isolate stack gap-10" style={{ listStyle: 'none' }}>
            {posts.slice(0, 20).map(post => {
              const parts = Object.entries(post.components ?? {})
              const total = Number(post.outcome_score ?? 0)
              return (
                <li
                  key={post.slug}
                  className="isolate-item tip row gap-14"
                  data-tip={parts.map(([k, v]) => `${k} ${v.toFixed(2)}`).join('  ·  ') || 'no component breakdown stored'}
                >
                  <span className="truncate t-base" style={{ flex: 1, minWidth: 0, color: 'var(--ink-2)' }}>
                    {post.title}
                    {post.matured === false && (
                      <span className="chip chip--amber" style={{ marginLeft: 8, fontSize: 10.5, padding: '2px 8px' }}>
                        still ramping
                      </span>
                    )}
                  </span>
                  <span
                    className="row"
                    style={{ width: 220, flex: 'none', height: 17, background: 'var(--bg)', borderRadius: 5, overflow: 'hidden' }}
                  >
                    {parts.map(([key, value]) => (
                      <span
                        key={key}
                        style={{
                          width: `${(Math.max(0, value) / scoreMax) * 100}%`,
                          background: COMPONENT_COLOURS[key] ?? 'var(--ink-faint)',
                          opacity: .85,
                        }}
                      />
                    ))}
                  </span>
                  <span className="mono t-sm" style={{ width: 44, textAlign: 'right', flex: 'none', color: 'var(--ink-2)' }}>
                    {total.toFixed(2)}
                  </span>
                </li>
              )
            })}
          </ul>
          <ul className="chart-legend" style={{ marginTop: 14 }}>
            {Object.entries(COMPONENT_COLOURS).map(([key, colour]) => (
              <li key={key}>
                <span className="legend-key" style={{ cursor: 'default' }}>
                  <span className="legend-swatch" style={{ background: colour }} aria-hidden="true" />
                  <span className="legend-label">{key}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="grid-halves">
        <section className="card rise" style={{ '--i': 5 } as React.CSSProperties}>
          <h2 className="section-title">What the scout found</h2>
          <p className="section-note" style={{ marginBottom: 16 }}>
            Signals swept from outside sources, then gated against the brand vocabulary.
            {scout.lastSweep ? ` Last sweep ${relative(scout.lastSweep)}.` : ''}
          </p>

          {scout.bySource.length > 0 && (
            <div className="row wrap gap-18 mb-18">
              {scout.bySource.map(s => (
                <span key={s.source} className="t-sm" style={{ color: 'var(--ink-mute)' }}>
                  <strong style={{ color: 'var(--ink)' }}>{s.count}</strong> {s.source}
                </span>
              ))}
            </div>
          )}

          {scout.accepted.length === 0 && scout.rejected.length === 0 ? (
            <p className="t-base muted">The scout has not swept yet.</p>
          ) : (
            <>
              <h3 className="t-base" style={{ fontWeight: 600, color: 'var(--teal-ink)', marginBottom: 10 }}>
                Passed the gate
              </h3>
              <ul className="stack gap-8 mb-18" style={{ listStyle: 'none' }}>
                {scout.accepted.slice(0, 8).map(signal => (
                  <li
                    key={signal.title}
                    className="row gap-12"
                    style={{ alignItems: 'baseline', background: 'var(--surface-sunk)', borderRadius: 12, padding: '10px 13px' }}
                  >
                    <span className="display tnum" style={{ fontSize: 13, fontWeight: 700, width: 26, flex: 'none', color: 'var(--lav-ink)' }}>
                      {signal.score !== null ? Math.round(signal.score) : '—'}
                    </span>
                    <span className="t-base" style={{ flex: 1, minWidth: 0, color: 'var(--ink-2)', lineHeight: 1.45 }}>
                      {signal.title}
                    </span>
                    <span className="mono t-xs" style={{ color: 'var(--ink-mute)', flex: 'none' }}>
                      {signal.platform ?? signal.source}{signal.cluster ? ` · ${signal.cluster}` : ''}
                    </span>
                  </li>
                ))}
              </ul>

              <h3 className="t-base" style={{ fontWeight: 600, color: 'var(--ink-3)', marginBottom: 9 }}>
                Rejected — shown so you can tell “nothing was trending” from “the gate is too tight”
              </h3>
              <ul className="stack gap-6" style={{ listStyle: 'none' }}>
                {scout.rejected.slice(0, 8).map(signal => (
                  <li key={signal.title} className="t-sm" style={{ color: 'var(--ink-mute)', lineHeight: 1.5 }}>
                    <span style={{ textDecoration: 'line-through' }}>{signal.title}</span>
                    {signal.reject_reason && <> — <em>{signal.reject_reason}</em></>}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

        <section className="card rise" style={{ '--i': 6 } as React.CSSProperties}>
          <h2 className="section-title">Format mix</h2>
          <p className="section-note mb-18">
            Which shapes the site actually publishes in. Format is recorded on every post but is
            deliberately not a bandit dimension yet — splitting the arms again at this sample size
            would leave nearly every cell under one observation.
          </p>
          {formats.length === 0 ? (
            <p className="t-base muted">No formats recorded yet.</p>
          ) : (
            <>
              <ul className="isolate stack gap-12" style={{ listStyle: 'none' }}>
                {formats.map((format, i) => (
                  <li
                    key={format.format}
                    className="isolate-item tip row gap-14"
                    data-tip={`${format.format} — ${format.total} topic${format.total === 1 ? '' : 's'} ever, ${format.published} published`}
                  >
                    <span className="mono t-sm truncate" style={{ width: 118, flex: 'none', color: 'var(--ink-2)' }}>
                      {format.format}
                    </span>
                    <span className="track track--thick" style={{ flex: 1, height: 18 }}>
                      <span
                        className="track-fill bar-grow-x"
                        style={{
                          display: 'block',
                          width: `${(format.total / formatMax) * 100}%`,
                          background: Object.values(COMPONENT_COLOURS)[i % 5],
                          opacity: .78,
                          borderRadius: 6,
                          '--i': i,
                        } as React.CSSProperties}
                      />
                    </span>
                    <span className="t-sm muted" style={{ width: 132, textAlign: 'right', flex: 'none' }}>
                      {format.total} total · {format.published} published
                    </span>
                  </li>
                ))}
              </ul>

              {topFormat && publishedTotal > 0 && (
                <p className="notice notice--amber t-sm" style={{ marginTop: 16, lineHeight: 1.6 }}>
                  {Math.round((topFormat.published / publishedTotal) * 100)}% of published posts are{' '}
                  {topFormat.format}s. There is no format variety to learn from yet — the engine
                  cannot tell you which format works until the site publishes more than one.
                </p>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  )
}
