import { NextResponse, type NextRequest } from 'next/server'
import { SESSION_COOKIE, verifySession, authConfig, allowUnconfigured } from './lib/auth'

/**
 * Gate every dashboard page and API route behind a session.
 *
 * Before this file existed the whole surface was public: `/api/run`,
 * `/api/approve`, `/api/reject`, `/api/delete` and `/api/reset` all accepted
 * unauthenticated POSTs against a live publishing pipeline.
 *
 * Three paths stay open, each for a stated reason:
 *   /login, /api/login    the way in
 *   /api/track            called cross-origin by the published blog; it takes no
 *                         action beyond inserting a view row and is separately
 *                         rate-limited and validated
 *   /api/autopilot/*      called by the GitHub Actions cron, which cannot hold a
 *                         browser session; those routes check a bearer secret
 *                         themselves
 *   /api/analytics/*      same reason — the daily ingest cron authenticates with
 *                         the same bearer secret inside the route
 *   /api/privacy/*        the retention purge cron, likewise
 *
 * Every one of these checks a bearer secret inside its own handler. Adding a
 * prefix here without that check would publish the route.
 */
const PUBLIC_PATHS = new Set(['/login', '/api/login', '/api/logout'])
const PUBLIC_PREFIXES = [
  '/api/track', '/api/autopilot/', '/api/analytics/', '/api/privacy/',
  '/brand/', '/_next/', '/favicon',
]

function isPublic(pathname: string): boolean {
  if (PUBLIC_PATHS.has(pathname)) return true
  return PUBLIC_PREFIXES.some(prefix => pathname.startsWith(prefix))
}

function unauthorized(request: NextRequest, reason: string): NextResponse {
  // APIs get a machine-readable 401; pages get bounced to the login form with a
  // return path, so a deep link survives the round trip.
  if (request.nextUrl.pathname.startsWith('/api/')) {
    return NextResponse.json({ error: 'unauthorized', reason }, { status: 401 })
  }
  const loginUrl = new URL('/login', request.url)
  const target = request.nextUrl.pathname + request.nextUrl.search
  if (target && target !== '/') loginUrl.searchParams.set('next', target)
  return NextResponse.redirect(loginUrl)
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl
  if (isPublic(pathname)) return NextResponse.next()

  const { secret, configured } = authConfig()

  if (!configured) {
    if (allowUnconfigured()) {
      console.warn(
        '[auth] APP_SECRET and/or DASHBOARD_PASSWORD are unset — the dashboard is ' +
          'UNPROTECTED. This is allowed in development only; production fails closed.',
      )
      return NextResponse.next()
    }
    console.error('[auth] APP_SECRET and/or DASHBOARD_PASSWORD unset in production — denying all requests.')
    return unauthorized(request, 'auth_not_configured')
  }

  const session = await verifySession(request.cookies.get(SESSION_COOKIE)?.value, secret)
  if (!session) return unauthorized(request, 'no_session')

  return NextResponse.next()
}

export const config = {
  // Everything except Next's own static output. Route-level exemptions are
  // handled in isPublic() above so they are visible in one place.
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
