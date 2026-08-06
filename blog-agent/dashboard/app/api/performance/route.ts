import { NextResponse } from 'next/server'
import { supabaseAdmin } from '../../../lib/supabase'

export const dynamic = 'force-dynamic'

/**
 * Search + engagement performance, per post, with the provenance of each topic.
 *
 * Reads the tables `run.py --ingest-analytics` fills. Everything here is
 * aggregation of stored facts — no scoring, no model. The learning layer lives
 * at /api/learning and is computed in Python, so the formula that ranks the
 * queue and the numbers shown on screen can never drift apart.
 */

const WINDOW = 28
const DAY_MS = 86_400_000

type MetricRow = {
  date: string
  slug: string
  source: string
  impressions: number | null
  clicks: number | null
  position: number | null
  views: number | null
  users: number | null
  engagement_rate: number | null
}

type QueryRow = {
  date: string
  slug: string
  query: string
  impressions: number | null
  clicks: number | null
  position: number | null
}

/** Impression-weighted accumulator. Search Console reports position as a
 *  per-impression average, so summing rows means weighting by impressions —
 *  a plain mean invents a rank the site never held, always optimistically. */
class Agg {
  impressions = 0
  clicks = 0
  views = 0
  users = 0
  private posWeight = 0
  private erWeight = 0

  addSearch(r: { impressions: number | null; clicks: number | null; position: number | null }): void {
    const imp = r.impressions || 0
    this.impressions += imp
    this.clicks += r.clicks || 0
    this.posWeight += (r.position || 0) * imp
  }

  addEngagement(r: { views: number | null; users: number | null; engagement_rate: number | null }): void {
    const v = r.views || 0
    this.views += v
    this.users += r.users || 0
    this.erWeight += (r.engagement_rate || 0) * v
  }

  get ctr(): number | null {
    return this.impressions ? this.clicks / this.impressions : null
  }

  get position(): number | null {
    return this.impressions ? this.posWeight / this.impressions : null
  }

  get engagementRate(): number | null {
    return this.views ? this.erWeight / this.views : null
  }

  toJSON() {
    return {
      impressions: this.impressions,
      clicks: this.clicks,
      ctr: this.ctr === null ? null : round(this.ctr, 4),
      position: this.position === null ? null : round(this.position, 1),
      views: this.views,
      users: this.users,
      engagementRate: this.engagementRate === null ? null : round(this.engagementRate, 4),
    }
  }
}

const round = (n: number, dp: number): number => Math.round(n * 10 ** dp) / 10 ** dp
const dayKey = (d: Date): string => d.toISOString().slice(0, 10)

function daysAgo(n: number): string {
  return dayKey(new Date(Date.now() - n * DAY_MS))
}

/**
 * Percentage change, or null when a percentage would mislead.
 *
 * Two cases return null, both rendered as "new" rather than a number:
 *   - no baseline at all (0 → 8 clicks is not "infinity percent")
 *   - a baseline too small to divide by. Going 5 → 1004 impressions is a real
 *     event, but "▲ 19980%" reads as a rendering fault, and next week the same
 *     growth against a bigger base shows a smaller number — which inverts the
 *     signal. Below MIN_BASELINE the absolute figures alongside tell the story
 *     better than a ratio can.
 */
const MIN_BASELINE = 10

function delta(now: number, before: number): number | null {
  if (before < MIN_BASELINE) return now === before ? 0 : null
  return round(((now - before) / before) * 100, 1)
}

export async function GET() {
  try {
    const since = daysAgo(WINDOW * 2)

    const [topicsRes, postsRes, metricsRes, queriesRes] = await Promise.all([
      supabaseAdmin.from('topics')
        .select('id,slug,title,status,tags,target_keyword,source_kind,source_detail')
        .limit(5000),
      supabaseAdmin.from('blog_posts')
        .select('topic_id,published_at,published_url,word_count')
        .limit(5000),
      supabaseAdmin.from('post_metrics_daily')
        .select('date,slug,source,impressions,clicks,position,views,users,engagement_rate')
        .gte('date', since).limit(100000),
      supabaseAdmin.from('post_queries_daily')
        .select('date,slug,query,impressions,clicks,position')
        .gte('date', daysAgo(WINDOW)).limit(100000),
    ])

    if (topicsRes.error) throw topicsRes.error

    const topics = topicsRes.data || []
    const posts = postsRes.data || []
    // Metrics tables are empty until the first ingest runs. That is a normal
    // pre-launch state, not an error — the page renders its empty state.
    const metrics = (metricsRes.error ? [] : metricsRes.data || []) as MetricRow[]
    const queries = (queriesRes.error ? [] : queriesRes.data || []) as QueryRow[]

    const cutoff = daysAgo(WINDOW)

    // ── topic/post lookup ──────────────────────────────────────────────────
    const bySlug = new Map<string, (typeof topics)[number]>()
    for (const t of topics) bySlug.set(t.slug, t)

    const slugById = new Map<string, string>()
    for (const t of topics) slugById.set(t.id, t.slug)

    const publishedAt = new Map<string, string>()
    const urlBySlug = new Map<string, string>()
    for (const p of posts) {
      const slug = slugById.get(p.topic_id)
      if (!slug) continue
      if (p.published_at) publishedAt.set(slug, p.published_at)
      if (p.published_url) urlBySlug.set(slug, p.published_url)
    }

    // ── aggregate per post, current window vs the one before it ────────────
    const current = new Map<string, Agg>()
    const previous = new Map<string, Agg>()
    const byDay = new Map<string, { impressions: number; clicks: number }>()

    const slot = (m: Map<string, Agg>, k: string): Agg => {
      let a = m.get(k)
      if (!a) { a = new Agg(); m.set(k, a) }
      return a
    }

    for (const row of metrics) {
      const inWindow = row.date >= cutoff
      const target = inWindow ? current : previous

      if (row.source === 'gsc') {
        slot(target, row.slug).addSearch(row)
        if (inWindow) {
          const d = byDay.get(row.date) || { impressions: 0, clicks: 0 }
          d.impressions += row.impressions || 0
          d.clicks += row.clicks || 0
          byDay.set(row.date, d)
        }
      } else if (row.source === 'ga4') {
        slot(target, row.slug).addEngagement(row)
      }
    }

    // ── site totals ────────────────────────────────────────────────────────
    const totalNow = new Agg()
    const totalPrev = new Agg()
    for (const [, a] of current) {
      totalNow.impressions += a.impressions
      totalNow.clicks += a.clicks
      totalNow.views += a.views
    }
    for (const [, a] of previous) {
      totalPrev.impressions += a.impressions
      totalPrev.clicks += a.clicks
      totalPrev.views += a.views
    }
    // Site-wide position is re-derived from the per-post rows so it stays
    // impression-weighted across posts as well as within them.
    const sitePos = new Agg()
    for (const row of metrics) {
      if (row.source === 'gsc' && row.date >= cutoff) sitePos.addSearch(row)
    }

    const series = Array.from({ length: WINDOW }, (_, i) => {
      const date = daysAgo(WINDOW - 1 - i)
      const d = byDay.get(date) || { impressions: 0, clicks: 0 }
      return { date, ...d }
    })

    // ── per-post leaderboard ───────────────────────────────────────────────
    const now = Date.now()
    const leaderboard = Array.from(current.entries()).map(([slug, agg]) => {
      const topic = bySlug.get(slug)
      const prev = previous.get(slug)
      const pub = publishedAt.get(slug)
      const detail = (topic?.source_detail || {}) as Record<string, unknown>
      return {
        slug,
        title: topic?.title || slug,
        url: urlBySlug.get(slug) || null,
        publishedAt: pub || null,
        ageDays: pub ? Math.floor((now - new Date(pub).getTime()) / DAY_MS) : null,
        tags: topic?.tags || [],
        targetKeyword: topic?.target_keyword || null,
        sourceKind: topic?.source_kind || null,
        sourcePlatform: (detail.platform as string) || null,
        sourceUrl: (detail.url as string) || null,
        ...agg.toJSON(),
        impressionsDelta: delta(agg.impressions, prev?.impressions || 0),
        clicksDelta: delta(agg.clicks, prev?.clicks || 0),
      }
    }).sort((a, b) => b.impressions - a.impressions)

    // ── what each post actually ranks for ──────────────────────────────────
    const perPostQueries = new Map<string, Map<string, Agg>>()
    for (const row of queries) {
      let m = perPostQueries.get(row.slug)
      if (!m) { m = new Map(); perPostQueries.set(row.slug, m) }
      slot(m, row.query).addSearch(row)
    }
    const topQueries: Record<string, { query: string; impressions: number; clicks: number; position: number | null }[]> = {}
    for (const [slug, m] of perPostQueries) {
      topQueries[slug] = Array.from(m.entries())
        .map(([query, a]) => ({
          query,
          impressions: a.impressions,
          clicks: a.clicks,
          position: a.position === null ? null : round(a.position, 1),
        }))
        .sort((a, b) => b.impressions - a.impressions)
        .slice(0, 8)
    }

    // ── opportunities ──────────────────────────────────────────────────────
    // Page 2 with real impressions is the highest-ROI SEO position there is:
    // demand is already proven, and a title/meta/depth pass moves it to page 1
    // without earning a single backlink.
    const pageTwo = leaderboard
      .filter(p => p.position !== null && p.position > 10 && p.position <= 20 && p.impressions >= 10)
      .map(p => ({ ...p, fix: 'Page 2 with proven demand — rewrite title/meta, add depth' }))
      .slice(0, 10)

    // Ranking well but nobody clicks: the listing is not answering the query.
    const lowCtr = leaderboard
      .filter(p => p.position !== null && p.position <= 10 && p.impressions >= 20 && (p.ctr ?? 1) < 0.02)
      .map(p => ({ ...p, fix: 'Ranks on page 1 but is not clicked — the title is not matching intent' }))
      .slice(0, 10)

    // Ranking for something other than what it was written to rank for.
    const intentDrift = leaderboard
      .filter(p => p.targetKeyword && p.impressions >= 10)
      .map(p => {
        const top = (topQueries[p.slug] || [])[0]
        if (!top) return null
        const target = p.targetKeyword!.toLowerCase().trim()
        const actual = top.query.toLowerCase().trim()
        const overlap = target.split(/\s+/).filter(w => w.length > 3 && actual.includes(w)).length
        if (overlap > 0) return null
        return {
          slug: p.slug, title: p.title, targetKeyword: p.targetKeyword,
          actualTopQuery: top.query, impressions: top.impressions,
          fix: 'Ranks for a different intent than it targeted — retarget or split the post',
        }
      })
      .filter(Boolean)
      .slice(0, 10)

    // ── performance by where the topic came from ───────────────────────────
    // The question the whole provenance layer exists to answer.
    const sourceAgg = new Map<string, { agg: Agg; posts: number }>()
    for (const p of leaderboard) {
      const key = p.sourcePlatform && p.sourceKind
        ? `${p.sourceKind}:${p.sourcePlatform}`
        : p.sourceKind || 'unknown'
      let entry = sourceAgg.get(key)
      if (!entry) { entry = { agg: new Agg(), posts: 0 }; sourceAgg.set(key, entry) }
      entry.agg.impressions += p.impressions
      entry.agg.clicks += p.clicks
      entry.posts += 1
    }
    const bySource = Array.from(sourceAgg.entries())
      .map(([source, { agg, posts }]) => ({
        source,
        posts,
        impressions: agg.impressions,
        clicks: agg.clicks,
        impressionsPerPost: posts ? Math.round(agg.impressions / posts) : 0,
      }))
      .sort((a, b) => b.impressionsPerPost - a.impressionsPerPost)

    const lastIngest = metrics.reduce<string | null>(
      (max, r) => (!max || r.date > max ? r.date : max), null,
    )

    return NextResponse.json({
      generatedAt: new Date().toISOString(),
      windowDays: WINDOW,
      hasData: metrics.length > 0,
      lastIngestDate: lastIngest,
      totals: {
        impressions: totalNow.impressions,
        clicks: totalNow.clicks,
        ctr: totalNow.impressions ? round(totalNow.clicks / totalNow.impressions, 4) : null,
        position: sitePos.position === null ? null : round(sitePos.position, 1),
        views: totalNow.views,
        impressionsDelta: delta(totalNow.impressions, totalPrev.impressions),
        clicksDelta: delta(totalNow.clicks, totalPrev.clicks),
        viewsDelta: delta(totalNow.views, totalPrev.views),
      },
      series,
      posts: leaderboard,
      topQueries,
      opportunities: { pageTwo, lowCtr, intentDrift },
      bySource,
      publishedCount: topics.filter(t => t.status === 'published').length,
    })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'failed to build performance report'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
