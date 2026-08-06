import { NextResponse } from 'next/server'
import { supabaseAdmin } from '../../../lib/supabase'

export const dynamic = 'force-dynamic'

/**
 * What the engine currently believes, and why.
 *
 * Pure read. Every number here was computed by `run.py --learn` in Python and
 * stored — the dashboard never recomputes a score. That is deliberate: the
 * formula that ranks the production queue and the formula behind these charts
 * must be the same one, or the page becomes a plausible-looking fiction.
 */
export async function GET() {
  try {
    const [armsRes, scoresRes, decisionsRes, snapsRes, topicsRes, signalsRes] = await Promise.all([
      supabaseAdmin.from('bandit_arms').select('*').limit(200),
      supabaseAdmin.from('post_scores').select('*').order('outcome_score', { ascending: false }).limit(500),
      supabaseAdmin.from('topic_decisions').select('*').order('at', { ascending: false }).limit(120),
      supabaseAdmin.from('learning_snapshots').select('*').order('at', { ascending: false }).limit(30),
      supabaseAdmin.from('topics').select('slug,title,content_format,status').limit(5000),
      supabaseAdmin.from('scout_signals')
        .select('fingerprint,source,platform,geo,title,url,summary,score,relevance,cluster,status,reject_reason,last_seen')
        .order('score', { ascending: false }).limit(200),
    ])

    // Every table here is empty until the first `--learn` run. That is a normal
    // pre-launch state, so an error reads as "no data yet" rather than failing
    // the whole page.
    const arms = armsRes.error ? [] : armsRes.data || []
    const scores = scoresRes.error ? [] : scoresRes.data || []
    const decisions = decisionsRes.error ? [] : decisionsRes.data || []
    const snapshots = snapsRes.error ? [] : snapsRes.data || []
    const topics = topicsRes.error ? [] : topicsRes.data || []

    const signals = signalsRes.error ? [] : signalsRes.data || []

    const titleBySlug = new Map<string, string>()
    for (const t of topics) titleBySlug.set(t.slug, t.title)

    // Format mix. Currently the most useful thing this block reveals is how
    // *little* variety there is — a site writing one format cannot learn which
    // format works, and no amount of data fixes that.
    const formatCounts: Record<string, { total: number; published: number }> = {}
    for (const t of topics) {
      const key = t.content_format || 'unclassified'
      const slot = formatCounts[key] || { total: 0, published: 0 }
      slot.total += 1
      if (t.status === 'published') slot.published += 1
      formatCounts[key] = slot
    }
    const formats = Object.entries(formatCounts)
      .map(([format, v]) => ({ format, ...v }))
      .sort((a, b) => b.total - a.total)

    const latest = snapshots[0] || null
    const config = (latest?.config || {}) as Record<string, unknown>
    const matured = Number(latest?.posts_matured ?? 0)
    const threshold = Number(config.min_posts_to_act ?? 25)
    const bandiActive = Boolean(config.bandit_active)

    // Only the most recent ranking is a live opinion; older rows are history.
    const latestAt = decisions[0]?.at ?? null
    const currentRanking = decisions
      .filter(d => d.at === latestAt)
      .sort((a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9))
      .map(d => ({ ...d, title: titleBySlug.get(d.slug) || d.slug }))

    return NextResponse.json({
      generatedAt: new Date().toISOString(),
      hasRun: snapshots.length > 0,
      status: {
        mode: bandiActive && matured >= threshold ? 'active' : 'shadow',
        bandiActive,
        matured,
        threshold,
        scored: Number(latest?.posts_scored ?? 0),
        armCount: arms.length,
        globalRate: latest?.global_rate ?? null,
        lastRunAt: latest?.at ?? null,
        // Why it is not steering yet, in the same words the CLI uses.
        reason: !latest
          ? 'The learning run has never been executed.'
          : matured < threshold
            ? `${matured} of ${threshold} matured posts. Below this the posterior is mostly prior, so acting on it would be acting on an assumption.`
            : !bandiActive
              ? 'Enough data, but LEARN_BANDIT_ACTIVE is not set to true.'
              : 'The bandit is ordering the production queue.',
      },
      arms: arms
        .map(a => ({
          ...a,
          uncertainty: Number(a.ci_high ?? 0) - Number(a.ci_low ?? 0),
        }))
        .sort((a, b) => Number(b.mean ?? 0) - Number(a.mean ?? 0)),
      posts: scores.map(s => ({ ...s, title: titleBySlug.get(s.slug) || s.slug })),
      ranking: currentRanking,
      history: decisions.map(d => ({ ...d, title: titleBySlug.get(d.slug) || d.slug })),
      calibration: latest?.calibration ?? { buckets: [], brier: null, n: 0 },
      snapshots: snapshots.slice().reverse(),
      formats,
      scout: {
        // Rejections are shown alongside accepts on purpose: an empty topic
        // queue looks identical whether nothing was trending or the relevance
        // gate was set too tight, and only the reject list tells you which.
        accepted: signals.filter(s => s.status === 'new').slice(0, 25),
        rejected: signals.filter(s => s.status === 'rejected').slice(0, 15),
        lastSweep: signals.reduce<string | null>(
          (max, s) => (!max || s.last_seen > max ? s.last_seen : max), null),
        bySource: Object.entries(
          signals.reduce<Record<string, number>>((acc, s) => {
            acc[s.source] = (acc[s.source] || 0) + 1
            return acc
          }, {}),
        ).map(([source, count]) => ({ source, count })).sort((a, b) => b.count - a.count),
      },
      config,
    })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'failed to build learning report'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
