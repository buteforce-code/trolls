'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { fmtISTLong } from '../../lib/datetime'

// ── Types (mirror /api/learning) ───────────────────────────────────────────
type Arm = {
  arm: string; cluster: string; source_platform: string
  alpha: number; beta: number; trials: number; successes: number
  mean: number; ci_low: number; ci_high: number; uncertainty: number
  density: { x: number; y: number }[]
}
type Score = {
  slug: string; title: string; cluster: string; source_platform: string | null
  age_days: number | null; matured: boolean
  impressions: number; clicks: number; position: number | null
  outcome_score: number; success: boolean
  components: Record<string, number>
}
type Decision = {
  slug: string; title: string; arm: string; mode: string; rank: number
  sampled: number; applied: boolean; at: string
  explanation: { reason?: string; posterior_mean?: number; observations?: number }
}
type Report = {
  hasRun: boolean
  status: {
    mode: string; bandiActive: boolean; matured: number; threshold: number
    scored: number; armCount: number; globalRate: number | null
    lastRunAt: string | null; reason: string
  }
  arms: Arm[]
  posts: Score[]
  ranking: Decision[]
  calibration: { buckets: { range: string; predicted: number; actual: number; n: number }[]; brier: number | null; n: number }
  snapshots: { at: string; posts_matured: number; arms: number; global_rate: number }[]
  formats: { format: string; total: number; published: number }[]
  scout: {
    accepted: Signal[]
    rejected: Signal[]
    lastSweep: string | null
    bySource: { source: string; count: number }[]
  }
}
type Signal = {
  fingerprint: string; source: string; platform: string; geo: string
  title: string; url: string | null; summary: string | null
  score: number; relevance: number; cluster: string
  status: string; reject_reason: string | null; last_seen: string
}

const ARM_COLORS = [
  '#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#14b8a6',
]
const pctFmt = (v: number | null | undefined): string =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(0)}%`

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="card" style={{ padding: 20, marginBottom: 18 }}>
      <h2 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>{title}</h2>
      {subtitle && <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 14px', maxWidth: 760, lineHeight: 1.5 }}>{subtitle}</p>}
      {children}
    </div>
  )
}

/**
 * The belief chart — overlaid Beta posteriors, one curve per arm.
 *
 * This is the whole reason a bandit was chosen over a neural policy. A tall,
 * narrow curve means "confident"; a low, wide one means "still guessing". You
 * can read the engine's actual state of knowledge off the picture instead of
 * being handed a number and asked to trust it.
 */
function BeliefChart({ arms }: { arms: Arm[] }) {
  const W = 720
  const H = 240
  const PAD = { l: 44, r: 12, t: 12, b: 34 }
  const plotW = W - PAD.l - PAD.r
  const plotH = H - PAD.t - PAD.b

  const maxY = Math.max(1, ...arms.flatMap(a => a.density.map(p => p.y)))
  const x = (v: number) => PAD.l + v * plotW
  const y = (v: number) => PAD.t + plotH - (v / maxY) * plotH

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', minWidth: 520, height: 'auto' }} role="img"
           aria-label="Posterior belief distribution for each content arm">
        {[0, 0.25, 0.5, 0.75, 1].map(t => (
          <g key={t}>
            <line x1={x(t)} y1={PAD.t} x2={x(t)} y2={PAD.t + plotH} stroke="var(--border)" strokeWidth={1} />
            <text x={x(t)} y={H - 14} fontSize={11} fill="var(--text-dim)" textAnchor="middle">
              {(t * 100).toFixed(0)}%
            </text>
          </g>
        ))}
        <text x={W / 2} y={H - 1} fontSize={10} fill="var(--text-dim)" textAnchor="middle">
          believed success rate
        </text>
        <text x={12} y={PAD.t + plotH / 2} fontSize={10} fill="var(--text-dim)"
              textAnchor="middle" transform={`rotate(-90 12 ${PAD.t + plotH / 2})`}>
          confidence
        </text>

        {arms.slice(0, 10).map((arm, i) => {
          const color = ARM_COLORS[i % ARM_COLORS.length]
          const path = arm.density.map((p, j) => `${j === 0 ? 'M' : 'L'}${x(p.x).toFixed(1)},${y(p.y).toFixed(1)}`).join(' ')
          return (
            <g key={arm.arm}>
              <path d={`${path} L${x(1)},${y(0)} L${x(0)},${y(0)} Z`} fill={color} opacity={0.07} />
              <path d={path} fill="none" stroke={color} strokeWidth={2} />
              <line x1={x(arm.mean)} y1={PAD.t + plotH} x2={x(arm.mean)} y2={PAD.t + plotH - 8}
                    stroke={color} strokeWidth={2} />
            </g>
          )
        })}
      </svg>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 16px', marginTop: 10 }}>
        {arms.slice(0, 10).map((arm, i) => (
          <div key={arm.arm} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <span style={{ width: 12, height: 3, background: ARM_COLORS[i % ARM_COLORS.length], borderRadius: 2 }} />
            <span style={{ fontFamily: 'var(--mono)' }}>{arm.arm}</span>
            <span style={{ color: 'var(--text-dim)' }}>
              {pctFmt(arm.mean)} ({pctFmt(arm.ci_low)}–{pctFmt(arm.ci_high)}) · n={Number(arm.trials).toFixed(1)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

/** Stacked contribution bar — which term actually produced a post's score. */
function ScoreBreakdown({ posts }: { posts: Score[] }) {
  const keys = ['impressions', 'clicks', 'position', 'ctr', 'engagement']
  const max = Math.max(0.001, ...posts.map(p => p.outcome_score))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
      {posts.map(p => (
        <div key={p.slug} style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 200px 60px', gap: 10, alignItems: 'center' }}>
          <span style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                title={p.title}>
            {p.title}
            {!p.matured && (
              <span style={{ marginLeft: 6, fontSize: 10, color: 'var(--amber)', border: '1px solid var(--amber)', padding: '1px 5px', borderRadius: 999 }}>
                still ramping
              </span>
            )}
          </span>
          <div style={{ display: 'flex', height: 16, background: 'var(--bg-hover)', borderRadius: 3, overflow: 'hidden' }}>
            {keys.map((k, i) => {
              const v = p.components?.[k] || 0
              if (v <= 0) return null
              return (
                <div key={k} title={`${k}: ${v.toFixed(2)}`}
                     style={{ width: `${(v / max) * 100}%`, background: ARM_COLORS[i], opacity: 0.85 }} />
              )
            })}
          </div>
          <span style={{ fontSize: 12, textAlign: 'right', fontFamily: 'var(--mono)' }}>
            {p.outcome_score.toFixed(2)}
          </span>
        </div>
      ))}
      <div style={{ display: 'flex', gap: 14, marginTop: 6, fontSize: 11, color: 'var(--text-dim)' }}>
        {keys.map((k, i) => (
          <span key={k} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 9, height: 9, background: ARM_COLORS[i], borderRadius: 2 }} />{k}
          </span>
        ))}
      </div>
    </div>
  )
}

/** Predicted vs actual. The chart that decides whether to trust the rest. */
function CalibrationChart({ calibration }: { calibration: Report['calibration'] }) {
  if (!calibration.buckets.length) {
    return <p style={{ fontSize: 13, color: 'var(--text-dim)', margin: 0 }}>
      Not enough matured posts to check calibration yet.
    </p>
  }
  const S = 200
  return (
    <div style={{ display: 'flex', gap: 24, alignItems: 'center', flexWrap: 'wrap' }}>
      <svg viewBox={`0 0 ${S} ${S}`} style={{ width: S, height: S }} role="img"
           aria-label="Predicted versus actual success rate">
        <rect x={0} y={0} width={S} height={S} fill="var(--bg-hover)" rx={4} />
        {/* Perfect calibration is the diagonal. Points above it mean the engine
            is under-confident; below, over-confident. */}
        <line x1={0} y1={S} x2={S} y2={0} stroke="var(--border-mid)" strokeDasharray="4 4" />
        {calibration.buckets.map(b => (
          <circle key={b.range} cx={b.predicted * S} cy={S - b.actual * S}
                  r={Math.max(4, Math.min(14, b.n * 2))}
                  fill="var(--accent)" opacity={0.65}>
            <title>{`${b.range}: predicted ${pctFmt(b.predicted)}, actual ${pctFmt(b.actual)} (n=${b.n})`}</title>
          </circle>
        ))}
      </svg>
      <div style={{ fontSize: 13 }}>
        <div style={{ fontSize: 26, fontWeight: 800 }}>
          {calibration.brier === null ? '—' : calibration.brier.toFixed(3)}
        </div>
        <div style={{ color: 'var(--text-muted)', marginBottom: 8 }}>Brier score over {calibration.n} posts</div>
        <div style={{ color: 'var(--text-dim)', maxWidth: 320, lineHeight: 1.5 }}>
          0 is a perfect forecast. 0.25 is what you get by always guessing 50%.
          Dots on the dashed line mean the engine&apos;s confidence matches reality —
          that is the bar it has to clear before it is allowed to reorder the queue.
        </div>
      </div>
    </div>
  )
}

// ── page ───────────────────────────────────────────────────────────────────
export default function LearningPage() {
  const [data, setData] = useState<Report | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/learning')
      .then(r => r.json())
      .then(d => (d.error ? setError(d.error) : setData(d)))
      .catch(e => setError(String(e)))
  }, [])

  if (error) return <main className="container"><div className="card" style={{ padding: 20, color: 'var(--red)' }}>{error}</div></main>
  if (!data) return <main className="container"><div className="card" style={{ padding: 20 }}>Loading…</div></main>

  const s = data.status
  const shadow = s.mode === 'shadow'

  return (
    <main className="container" style={{ paddingBottom: 60 }}>
      <header style={{ margin: '24px 0 18px' }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>Learning</h1>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>
          What the engine believes about its own content, and how it decides what to write next
          {s.lastRunAt && ` · last run ${fmtISTLong(s.lastRunAt)}`}
        </p>
      </header>

      <div className="card" style={{
        padding: 18, marginBottom: 18,
        borderLeft: `3px solid ${shadow ? 'var(--amber)' : 'var(--green)'}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{
            fontSize: 11, fontWeight: 700, letterSpacing: 0.6, textTransform: 'uppercase',
            padding: '3px 10px', borderRadius: 999,
            color: shadow ? 'var(--amber)' : 'var(--green)',
            border: `1px solid ${shadow ? 'var(--amber)' : 'var(--green)'}`,
          }}>{shadow ? 'Shadow mode' : 'Active'}</span>
          <span style={{ fontSize: 13 }}>{s.reason}</span>
        </div>
        <div style={{ display: 'flex', gap: 26, marginTop: 14, flexWrap: 'wrap', fontSize: 13 }}>
          <span><strong>{s.scored}</strong> <span style={{ color: 'var(--text-dim)' }}>posts scored</span></span>
          <span><strong>{s.matured}</strong> <span style={{ color: 'var(--text-dim)' }}>matured (of {s.threshold} needed)</span></span>
          <span><strong>{s.armCount}</strong> <span style={{ color: 'var(--text-dim)' }}>arms</span></span>
          <span><strong>{pctFmt(s.globalRate)}</strong> <span style={{ color: 'var(--text-dim)' }}>site-wide success rate</span></span>
        </div>
        {shadow && (
          <p style={{ fontSize: 12, color: 'var(--text-dim)', margin: '12px 0 0', lineHeight: 1.5 }}>
            The engine is still recording what it <em>would</em> choose. Publishing order is
            unchanged. Everything below is a live belief — it is just not being acted on yet.
          </p>
        )}
      </div>

      {!data.hasRun && (
        <div className="card" style={{ padding: 18, marginBottom: 18 }}>
          <strong style={{ fontSize: 14 }}>No learning run yet.</strong>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '6px 0 0' }}>
            Run <code>python run.py --ingest-analytics</code> then <code>python run.py --learn</code>.
          </p>
        </div>
      )}

      <Section
        title="What the engine believes"
        subtitle="One curve per arm — a content cluster paired with where its topics came from. A tall narrow curve means the engine is confident; a low wide one means it is still guessing and will keep exploring that arm. Every arm starts at the site-wide average and needs real evidence to move, which is what stops one viral post from capturing the whole system."
      >
        {data.arms.length === 0
          ? <p style={{ fontSize: 13, color: 'var(--text-dim)', margin: 0 }}>No arms fitted yet — no post has matured.</p>
          : <BeliefChart arms={data.arms} />}
      </Section>

      <Section
        title="What it would write next"
        subtitle="Queued topics ranked by Thompson sampling: each arm's belief is sampled once, and the highest draw wins. 'Explore' means the pick was driven by uncertainty rather than by evidence — that is the mechanism working, not a mistake."
      >
        {data.ranking.length === 0 ? (
          <p style={{ fontSize: 13, color: 'var(--text-dim)', margin: 0 }}>No queued topics to rank.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.ranking.slice(0, 10).map(d => (
              <div key={`${d.slug}-${d.rank}`} style={{
                display: 'grid', gridTemplateColumns: '30px minmax(0,1fr) 90px 110px', gap: 12,
                alignItems: 'center', padding: '8px 10px',
                background: d.rank === 1 ? 'var(--bg-hover)' : 'transparent',
                borderRadius: 'var(--radius-sm)',
                border: d.rank === 1 ? '1px solid var(--border-mid)' : '1px solid transparent',
              }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-dim)' }}>{d.rank}</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {d.title}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>{d.arm}</div>
                </div>
                <span style={{
                  fontSize: 11, fontWeight: 600, textAlign: 'center', padding: '2px 8px', borderRadius: 999,
                  color: d.mode === 'explore' ? 'var(--blue)' : 'var(--green)',
                  border: `1px solid ${d.mode === 'explore' ? 'var(--blue)' : 'var(--green)'}`,
                }}>{d.mode}</span>
                <span style={{ fontSize: 12, textAlign: 'right', color: 'var(--text-muted)' }}
                      title={d.explanation?.reason}>
                  draw {pctFmt(d.sampled)}
                </span>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section
        title="Why each post scored what it did"
        subtitle="The deterministic layer, shown term by term. Impressions and clicks enter through a log curve so one outlier cannot dominate; posts younger than 14 days are carried but not judged, because search rankings take weeks to settle."
      >
        {data.posts.length === 0
          ? <p style={{ fontSize: 13, color: 'var(--text-dim)', margin: 0 }}>No scored posts yet.</p>
          : <ScoreBreakdown posts={data.posts.slice(0, 15)} />}
      </Section>

      <Section
        title="Is it right?"
        subtitle="Calibration: when the engine says an arm succeeds 60% of the time, does it? This is the check that decides whether the beliefs above are worth acting on."
      >
        <CalibrationChart calibration={data.calibration} />
      </Section>

      <Section
        title="What the scout found"
        subtitle={
          `Signals swept from Hacker News, this site's own rising Search Console queries, and the Google Trends daily feed — then gated against the brand vocabulary. ` +
          (data.scout.lastSweep ? `Last sweep ${fmtISTLong(data.scout.lastSweep)}.` : 'No sweep has run yet.')
        }
      >
        {data.scout.accepted.length === 0 && data.scout.rejected.length === 0 ? (
          <p style={{ fontSize: 13, color: 'var(--text-dim)', margin: 0 }}>
            Nothing stored yet. Run <code>python run.py --scout</code>.
          </p>
        ) : (
          <>
            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 14 }}>
              {data.scout.bySource.map(s => (
                <span key={s.source} style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  <strong style={{ color: 'var(--text)' }}>{s.count}</strong> {s.source}
                </span>
              ))}
            </div>

            <h3 style={{ fontSize: 13, margin: '0 0 8px', color: 'var(--green)' }}>
              Passed the gate ({data.scout.accepted.length})
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 18 }}>
              {data.scout.accepted.slice(0, 10).map(s => (
                <div key={s.fingerprint} style={{
                  display: 'grid', gridTemplateColumns: '58px minmax(0,1fr) 110px', gap: 10,
                  alignItems: 'baseline', padding: '6px 8px',
                  background: 'var(--bg-hover)', borderRadius: 'var(--radius-sm)',
                }}>
                  <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--mono)' }}>
                    {Number(s.score).toFixed(0)}
                  </span>
                  <div style={{ minWidth: 0 }}>
                    {s.url ? (
                      <a href={s.url} target="_blank" rel="noreferrer"
                         style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>
                        {s.title}
                      </a>
                    ) : (
                      <span style={{ fontSize: 13 }}>{s.title}</span>
                    )}
                    {s.summary && (
                      <div style={{ fontSize: 11, color: 'var(--text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {s.summary}
                      </div>
                    )}
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'right' }}>
                    {s.platform} · {s.cluster}
                  </span>
                </div>
              ))}
            </div>

            <h3 style={{ fontSize: 13, margin: '0 0 8px', color: 'var(--text-muted)' }}>
              Rejected ({data.scout.rejected.length}) — shown so you can tell &ldquo;nothing was
              trending&rdquo; from &ldquo;the gate is too tight&rdquo;
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {data.scout.rejected.slice(0, 8).map(s => (
                <div key={s.fingerprint} style={{ fontSize: 12, color: 'var(--text-dim)' }}>
                  <span style={{ textDecoration: 'line-through' }}>{s.title.slice(0, 46)}</span>
                  {' — '}
                  <span style={{ fontStyle: 'italic' }}>{s.reject_reason}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </Section>

      <Section
        title="Format mix"
        subtitle="Which shapes the site actually publishes in. Format is recorded on every post but is deliberately not a bandit dimension yet — splitting the arms again at this sample size would leave nearly every cell with under one observation."
      >
        {data.formats.length === 0 ? (
          <p style={{ fontSize: 13, color: 'var(--text-dim)', margin: 0 }}>Nothing classified yet.</p>
        ) : (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {data.formats.map((f, i) => {
                const max = Math.max(...data.formats.map(x => x.total))
                return (
                  <div key={f.format} style={{ display: 'grid', gridTemplateColumns: '110px 1fr 130px', gap: 10, alignItems: 'center' }}>
                    <span style={{ fontSize: 13, fontFamily: 'var(--mono)' }}>{f.format}</span>
                    <div style={{ background: 'var(--bg-hover)', borderRadius: 4, height: 18, overflow: 'hidden' }}>
                      <div style={{
                        width: `${(f.total / max) * 100}%`, height: '100%',
                        background: ARM_COLORS[i % ARM_COLORS.length], opacity: 0.75,
                      }} />
                    </div>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'right' }}>
                      {f.total} total · {f.published} published
                    </span>
                  </div>
                )
              })}
            </div>
            {(() => {
              const published = data.formats.filter(f => f.published > 0)
              const total = published.reduce((a, f) => a + f.published, 0)
              const top = published.sort((a, b) => b.published - a.published)[0]
              if (!top || total === 0 || top.published / total < 0.8) return null
              return (
                <p style={{ fontSize: 12, color: 'var(--amber)', marginTop: 14, lineHeight: 1.5 }}>
                  {Math.round((top.published / total) * 100)}% of published posts are{' '}
                  <strong>{top.format}</strong>. There is no format variety to learn from —
                  the engine cannot tell you which format works until the site publishes more
                  than one.
                </p>
              )
            })()}
          </>
        )}
      </Section>
    </main>
  )
}
