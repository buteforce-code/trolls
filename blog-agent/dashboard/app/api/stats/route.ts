import { NextResponse } from 'next/server'
import { supabaseAdmin } from '../../../lib/supabase'

export const dynamic = 'force-dynamic'

// ── helpers ────────────────────────────────────────────────────────────────
const dayKey = (d: Date): string => d.toISOString().slice(0, 10)

/** Zero-filled [{date, count}] for the last `days` days, oldest → newest. */
function lastNDays(counts: Record<string, number>, days: number): { date: string; count: number }[] {
  const out: { date: string; count: number }[] = []
  const now = new Date()
  for (let i = days - 1; i >= 0; i -= 1) {
    const d = new Date(now)
    d.setUTCDate(now.getUTCDate() - i)
    const k = dayKey(d)
    out.push({ date: k, count: counts[k] || 0 })
  }
  return out
}

function parseMaybeJson(v: unknown): Record<string, unknown> | null {
  if (!v) return null
  if (typeof v === 'object') return v as Record<string, unknown>
  if (typeof v === 'string') {
    try { return JSON.parse(v) } catch { return null }
  }
  return null
}

function num(v: unknown): number | null {
  const n = typeof v === 'string' ? parseFloat(v) : typeof v === 'number' ? v : NaN
  return Number.isFinite(n) ? n : null
}

const avg = (xs: number[]): number | null =>
  xs.length ? Math.round((xs.reduce((a, b) => a + b, 0) / xs.length) * 10) / 10 : null

export async function GET() {
  try {
    const [topicsRes, postsRes, viewsRes] = await Promise.all([
      supabaseAdmin.from('topics').select('id,slug,title,status,tags,created_at,updated_at,scheduled_for').limit(5000),
      supabaseAdmin.from('blog_posts').select('topic_id,word_count,published_at,published_url,hero_image_url,schema_json,social_json,research_json,audit_json').limit(5000),
      supabaseAdmin.from('blog_views').select('slug,viewed_at').limit(100000),
    ])

    if (topicsRes.error) throw topicsRes.error
    if (postsRes.error) throw postsRes.error
    // blog_views may be empty / not yet receiving traffic — tolerate its error.
    const views = viewsRes.error ? [] : (viewsRes.data || [])

    const topics = topicsRes.data || []
    const posts = postsRes.data || []

    // ── maps ──────────────────────────────────────────────────────────────
    const titleBySlug: Record<string, string> = {}
    const slugById: Record<string, string> = {}
    for (const t of topics) {
      titleBySlug[t.slug] = t.title
      slugById[t.id] = t.slug
    }
    const urlBySlug: Record<string, string | null> = {}
    for (const p of posts) {
      const slug = slugById[p.topic_id]
      if (slug) urlBySlug[slug] = p.published_url ?? null
    }

    // ── status counts ───────────────────────────────────────────────────────
    const statusCounts: Record<string, number> = {}
    for (const t of topics) statusCounts[t.status] = (statusCounts[t.status] || 0) + 1
    const sc = (s: string) => statusCounts[s] || 0

    const totals = {
      topics: topics.length,
      published: sc('published'),
      scheduled: sc('scheduled'),
      queued: sc('queued'),
      needsReview: sc('verifying_research') + sc('verifying_draft'),
      failed: sc('failed'),
      inProgress: sc('researching') + sc('writing') + sc('publishing'),
    }

    // ── content quality ───────────────────────────────────────────────────────
    const wordCounts: number[] = []
    let withHero = 0, withSchema = 0, withSocial = 0
    const auditScores: number[] = []
    const confidences: number[] = []
    for (const p of posts) {
      const wc = num(p.word_count)
      if (wc && wc > 0) wordCounts.push(wc)
      if (p.hero_image_url) withHero += 1
      if (p.schema_json) withSchema += 1
      if (p.social_json) withSocial += 1
      const audit = parseMaybeJson(p.audit_json)
      const as = audit ? num(audit.score) : null
      if (as !== null) auditScores.push(as)
      const research = parseMaybeJson(p.research_json)
      const cs = research ? num(research.confidence_score) : null
      if (cs !== null && cs > 0) confidences.push(cs)
    }
    const sortedWc = [...wordCounts].sort((a, b) => a - b)
    const content = {
      posts: posts.length,
      totalWords: wordCounts.reduce((a, b) => a + b, 0),
      avgWords: avg(wordCounts),
      medianWords: sortedWc.length ? sortedWc[Math.floor(sortedWc.length / 2)] : null,
      withHeroImage: withHero,
      withSchema,
      withSocial,
      audited: auditScores.length,
      avgAuditScore: avg(auditScores),
      avgConfidence: avg(confidences),
    }

    // ── cadence ───────────────────────────────────────────────────────────────
    const pubByDay: Record<string, number> = {}
    let lastPublishedAt: string | null = null
    for (const p of posts) {
      if (!p.published_at) continue
      const d = new Date(p.published_at)
      pubByDay[dayKey(d)] = (pubByDay[dayKey(d)] || 0) + 1
      if (!lastPublishedAt || p.published_at > lastPublishedAt) lastPublishedAt = p.published_at
    }
    const upcoming = topics
      .filter(t => t.status === 'scheduled' && t.scheduled_for)
      .sort((a, b) => String(a.scheduled_for).localeCompare(String(b.scheduled_for)))
      .map(t => ({ slug: t.slug, title: t.title, scheduled_for: t.scheduled_for }))
    const cadence = {
      publishedByDay: lastNDays(pubByDay, 30),
      upcoming,
      lastPublishedAt,
      nextPublishAt: upcoming[0]?.scheduled_for ?? null,
    }

    // ── views ───────────────────────────────────────────────────────────────
    const now = Date.now()
    const D7 = now - 7 * 864e5
    const D30 = now - 30 * 864e5
    const viewsByDay: Record<string, number> = {}
    const viewsBySlug: Record<string, number> = {}
    let last7 = 0, last30 = 0
    for (const v of views) {
      const ts = new Date(v.viewed_at).getTime()
      viewsByDay[dayKey(new Date(v.viewed_at))] = (viewsByDay[dayKey(new Date(v.viewed_at))] || 0) + 1
      viewsBySlug[v.slug] = (viewsBySlug[v.slug] || 0) + 1
      if (ts >= D7) last7 += 1
      if (ts >= D30) last30 += 1
    }
    const topPosts = Object.entries(viewsBySlug)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([slug, v]) => ({ slug, title: titleBySlug[slug] || slug, views: v, published_url: urlBySlug[slug] ?? null }))
    const viewsBlock = {
      total: views.length,
      last7,
      last30,
      uniquePosts: Object.keys(viewsBySlug).length,
      byDay: lastNDays(viewsByDay, 30),
      topPosts,
      tracking: !viewsRes.error,
    }

    // ── tags ───────────────────────────────────────────────────────────────
    const tagCounts: Record<string, number> = {}
    for (const t of topics) for (const tag of t.tags || []) tagCounts[tag] = (tagCounts[tag] || 0) + 1
    const tags = Object.entries(tagCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([tag, count]) => ({ tag, count }))

    return NextResponse.json({
      generatedAt: new Date().toISOString(),
      totals,
      statusCounts,
      content,
      cadence,
      views: viewsBlock,
      tags,
    })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'failed to build stats'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
