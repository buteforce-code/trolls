import { NextResponse } from 'next/server'
import { SESSION_COOKIE } from '../../../lib/auth'

export const dynamic = 'force-dynamic'

export async function POST() {
  const response = NextResponse.json({ ok: true })
  // maxAge 0 expires the cookie immediately. Tokens are stateless, so this ends
  // the browser session; a copied token stays valid until its `exp`, which is
  // the accepted trade-off for not running a session store.
  response.cookies.set(SESSION_COOKIE, '', {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: 0,
  })
  return response
}
