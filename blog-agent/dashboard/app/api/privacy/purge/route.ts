import { NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { supabaseAdmin } from '../../../../lib/supabase'
import { retentionDays } from '../../../../lib/privacy'
import { SESSION_COOKIE, verifySession, authConfig, bearerMatches } from '../../../../lib/auth'

export const dynamic = 'force-dynamic'

/**
 * Enforce the view-data retention limit.
 *
 * Two callers: an authenticated operator from the dashboard, and the daily
 * GitHub Actions cron using AUTOPILOT_TICK_SECRET — which is why the bearer
 * path exists even though this route is not in the middleware's public list.
 *
 * This is a bulk-delete endpoint, so it verifies the session **itself** rather
 * than assuming the middleware ran. That assumption would be correct today and
 * silently wrong the moment someone adds `/api/privacy` to the public prefix
 * list or edits the middleware matcher.
 *
 * Retention is only real if something actually deletes. A documented policy with
 * no delete job is the thing regulators find.
 */
async function authorised(request: Request): Promise<boolean> {
  const header = request.headers.get('authorization') || ''
  if (header) {
    const secret = process.env.AUTOPILOT_TICK_SECRET || ''
    return bearerMatches(header, secret)
  }
  const { secret, configured } = authConfig()
  if (!configured) return false
  const jar = await cookies()
  return Boolean(await verifySession(jar.get(SESSION_COOKIE)?.value, secret))
}

export async function POST(request: Request): Promise<NextResponse> {
  if (!(await authorised(request))) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 })
  }

  const nowIso = new Date().toISOString()
  const cutoff = new Date(Date.now() - retentionDays() * 86_400_000).toISOString()

  // Rows written before `expires_at` existed carry NULL and would otherwise be
  // kept forever — exactly the failure this endpoint exists to prevent. They are
  // deleted on their own age instead.
  const { error: legacyError, count: legacyCount } = await supabaseAdmin
    .from('blog_views')
    .delete({ count: 'exact' })
    .is('expires_at', null)
    .lt('viewed_at', cutoff)

  const { error: expiredError, count: expiredCount } = await supabaseAdmin
    .from('blog_views')
    .delete({ count: 'exact' })
    .lte('expires_at', nowIso)

  const failure = legacyError || expiredError
  if (failure) {
    return NextResponse.json({ error: failure.message }, { status: 500 })
  }

  return NextResponse.json({
    ok: true,
    retentionDays: retentionDays(),
    deletedExpired: expiredCount ?? 0,
    deletedLegacy: legacyCount ?? 0,
    ranAt: nowIso,
  })
}
