import { NextResponse } from 'next/server'
import { supabaseAdmin } from '../../../lib/supabase'
import { rateLimit, clientKey } from '../../../lib/ratelimit'
import { pseudonymise, clientFamily, safeReferrer, expiresAt } from '../../../lib/privacy'

export const dynamic = 'force-dynamic'

// The published blog is a different origin (buteforce.com) from the dashboard,
// so this endpoint has to accept cross-origin posts. It is the only route
// exempted from the auth middleware, which is why everything it accepts is
// validated, rate-limited and minimised before it reaches the database.
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
}

// A real reader triggers one or two of these per page. 60/minute per IP leaves
// room for a busy office behind one NAT while making view-count inflation
// tedious enough not to be worth it.
const MAX_VIEWS_PER_MINUTE = 60

const MAX_FIELD = 256
// Must match the slugs the pipeline actually produces (see swarm/slugs.py).
const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,79}$/
const PATH_RE = /^\/[\w\-./]{0,200}$/

interface ViewInput {
  slug: string | null
  path: string | null
  referrer: string | null
  ua: string | null
  session: string | null
  event?: unknown
  scrollDepth?: unknown
  label?: unknown
}

const clean = (v: unknown): string | null =>
  typeof v === 'string' && v.trim() ? v.trim().slice(0, MAX_FIELD) : null

/** Only slugs this system could have generated are recorded. */
const validSlug = (v: unknown): string | null => {
  const s = clean(v)
  return s && SLUG_RE.test(s) ? s : null
}

const validPath = (v: unknown): string | null => {
  const s = clean(v)
  return s && PATH_RE.test(s) ? s : null
}

// Engagement events, closed set. Anything else is recorded as a plain view
// rather than rejected — a mislabelled event is still a real reader, and a
// client-side typo should not silently cost a datapoint.
const EVENTS = new Set(['view', 'scroll', 'cta'])
const SCROLL_MILESTONES = new Set([25, 50, 75, 100])

const validEvent = (v: unknown): string => {
  const s = typeof v === 'string' ? v.trim().toLowerCase() : ''
  return EVENTS.has(s) ? s : 'view'
}

/** Only the four milestones are stored. Accepting arbitrary percentages would
 *  let a client write unbounded values and turn a depth signal into noise. */
const validScroll = (v: unknown): number | null => {
  const n = typeof v === 'number' ? v : parseInt(String(v ?? ''), 10)
  return SCROLL_MILESTONES.has(n) ? n : null
}

async function record(input: ViewInput): Promise<boolean> {
  if (!input.slug) return false
  const event = validEvent(input.event)
  const { error } = await supabaseAdmin.from('blog_views').insert({
    slug: input.slug,
    path: input.path,
    referrer: safeReferrer(input.referrer),
    ua: clientFamily(input.ua),
    session_id: await pseudonymise(input.session),
    expires_at: expiresAt(),
    event,
    scroll_depth: event === 'scroll' ? validScroll(input.scrollDepth) : null,
    // Which CTA was clicked. Bounded and stripped of anything but a short label
    // so a page cannot smuggle free text or PII through this field.
    label: event === 'cta' ? (clean(input.label) || '').slice(0, 60) || null : null,
  })
  if (error) {
    console.error('[track] insert failed:', error.message)
    return false
  }
  return true
}

const limited = (request: Request): boolean =>
  !rateLimit(clientKey(request, 'track'), MAX_VIEWS_PER_MINUTE, 60).allowed

export async function OPTIONS(): Promise<NextResponse> {
  return new NextResponse(null, { status: 204, headers: CORS })
}

// JSON beacon — the published blog calls this on page load.
export async function POST(request: Request): Promise<NextResponse> {
  if (limited(request)) {
    return NextResponse.json({ ok: false, error: 'rate_limited' }, { status: 429, headers: CORS })
  }
  let body: Record<string, unknown> = {}
  try {
    body = await request.json()
  } catch {
    /* tolerate empty/invalid body */
  }
  const ok = await record({
    slug: validSlug(body.slug),
    path: validPath(body.path),
    referrer: clean(body.referrer) || clean(request.headers.get('referer')),
    ua: clean(request.headers.get('user-agent')),
    session: clean(body.session),
    event: body.event,
    scrollDepth: body.scrollDepth,
    label: body.label,
  })
  return NextResponse.json({ ok }, { status: ok ? 200 : 400, headers: CORS })
}

// 1x1 GIF pixel fallback for no-JS contexts: <img src=".../api/track?slug=my-post">
export async function GET(request: Request): Promise<NextResponse> {
  if (!limited(request)) {
    const { searchParams } = new URL(request.url)
    await record({
      slug: validSlug(searchParams.get('slug')),
      path: validPath(searchParams.get('path')),
      referrer: clean(request.headers.get('referer')),
      ua: clean(request.headers.get('user-agent')),
      session: null,
    })
  }
  // Always return the pixel, even when rate-limited or invalid — a broken image
  // on the client's blog would be a visible defect caused by our telemetry.
  const gif = Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64')
  return new NextResponse(gif, {
    status: 200,
    headers: {
      ...CORS,
      'Content-Type': 'image/gif',
      'Cache-Control': 'no-store, max-age=0',
    },
  })
}
