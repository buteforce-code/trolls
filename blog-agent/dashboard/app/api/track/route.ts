import { NextResponse } from 'next/server'
import { supabaseAdmin } from '../../../lib/supabase'

export const dynamic = 'force-dynamic'

// View counts are low-risk public telemetry; allow the published blog (a different
// origin, e.g. buteforce.com) to post events.
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
}

const MAX = 512
const clean = (v: unknown): string | null =>
  typeof v === 'string' && v.trim() ? v.trim().slice(0, MAX) : null

async function record(params: {
  slug: string | null
  path: string | null
  referrer: string | null
  ua: string | null
  session: string | null
}): Promise<boolean> {
  if (!params.slug) return false
  const { error } = await supabaseAdmin.from('blog_views').insert({
    slug: params.slug,
    path: params.path,
    referrer: params.referrer,
    ua: params.ua,
    session_id: params.session,
  })
  if (error) {
    console.error('[track] insert failed:', error.message)
    return false
  }
  return true
}

export async function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: CORS })
}

// JSON beacon — the published blog calls this on page load.
export async function POST(request: Request) {
  let body: Record<string, unknown> = {}
  try {
    body = await request.json()
  } catch {
    /* tolerate empty/invalid body */
  }
  const ok = await record({
    slug: clean(body.slug),
    path: clean(body.path),
    referrer: clean(body.referrer) || clean(request.headers.get('referer')),
    ua: clean(request.headers.get('user-agent')),
    session: clean(body.session),
  })
  return NextResponse.json({ ok }, { status: ok ? 200 : 400, headers: CORS })
}

// 1x1 GIF pixel fallback for no-JS contexts: <img src=".../api/track?slug=my-post">
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  await record({
    slug: clean(searchParams.get('slug')),
    path: clean(searchParams.get('path')),
    referrer: clean(request.headers.get('referer')),
    ua: clean(request.headers.get('user-agent')),
    session: null,
  })
  // Transparent 1x1 GIF.
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
