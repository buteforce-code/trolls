import { NextResponse } from 'next/server'
import { SESSION_COOKIE, SESSION_TTL_SECONDS, createSession, checkPassword, authConfig } from '../../../lib/auth'
import { rateLimit, clientKey } from '../../../lib/ratelimit'

export const dynamic = 'force-dynamic'

// Five attempts per five minutes per IP. Generous for a human who mistyped,
// useless for a script working through a wordlist.
const MAX_ATTEMPTS = 5
const WINDOW_SECONDS = 300

export async function POST(request: Request) {
  const limit = rateLimit(clientKey(request, 'login'), MAX_ATTEMPTS, WINDOW_SECONDS)
  if (!limit.allowed) {
    return NextResponse.json(
      { error: `Too many attempts. Try again in ${limit.retryAfterSeconds}s.` },
      { status: 429, headers: { 'Retry-After': String(limit.retryAfterSeconds) } },
    )
  }

  const { secret, password, configured } = authConfig()
  if (!configured) {
    return NextResponse.json(
      { error: 'Sign-in is not configured. Set APP_SECRET and DASHBOARD_PASSWORD.' },
      { status: 503 },
    )
  }

  let submitted = ''
  try {
    const body = await request.json()
    submitted = typeof body?.password === 'string' ? body.password : ''
  } catch {
    /* fall through to the generic failure below */
  }

  if (!(await checkPassword(submitted, password))) {
    // Deliberately identical whether the password was empty or merely wrong.
    return NextResponse.json({ error: 'Incorrect password.' }, { status: 401 })
  }

  const token = await createSession(secret)
  const response = NextResponse.json({ ok: true })
  response.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: SESSION_TTL_SECONDS,
  })
  return response
}
