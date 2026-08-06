/**
 * Session tokens for the Trolls dashboard.
 *
 * Why this exists
 * ---------------
 * Every dashboard route was public. `/api/run`, `/api/approve`, `/api/reject`,
 * `/api/delete` and `/api/reset` accepted unauthenticated POSTs, which meant
 * anyone who found the Render URL could publish to the live site, delete topics,
 * read unpublished drafts, and spawn Python jobs against the OpenAI key until
 * the budget ran out.
 *
 * Implementation notes
 * --------------------
 * Uses Web Crypto (`crypto.subtle`) rather than node:crypto so the same code
 * runs in Edge middleware and in Node route handlers. Tokens are stateless
 * HMAC-SHA256 — there is one operator, so a session store would be ceremony.
 *
 * Required env:
 *   APP_SECRET          long random string, signs the session cookie
 *   DASHBOARD_PASSWORD  the operator password
 */

export const SESSION_COOKIE = 'trolls_session'
export const SESSION_TTL_SECONDS = 12 * 60 * 60

export type SessionPayload = { sub: string; exp: number }

const encoder = new TextEncoder()

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function base64UrlDecode(input: string): Uint8Array {
  const padded = input.replace(/-/g, '+').replace(/_/g, '/')
  const binary = atob(padded + '='.repeat((4 - (padded.length % 4)) % 4))
  return Uint8Array.from(binary, c => c.charCodeAt(0))
}

async function hmac(secret: string, message: string): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )
  const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(message))
  return new Uint8Array(signature)
}

/**
 * Length-independent, value-constant-time comparison.
 *
 * Comparing lengths first would leak the length, so both sides are folded into a
 * fixed-width accumulator instead of short-circuiting on the first difference.
 */
export function timingSafeEqual(a: string, b: string): boolean {
  const maxLength = Math.max(a.length, b.length)
  let diff = a.length ^ b.length
  for (let i = 0; i < maxLength; i += 1) {
    diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0)
  }
  return diff === 0
}

/** Sign a session token valid for `ttlSeconds`. */
export async function createSession(
  secret: string,
  subject = 'operator',
  ttlSeconds = SESSION_TTL_SECONDS,
): Promise<string> {
  const payload: SessionPayload = {
    sub: subject,
    exp: Math.floor(Date.now() / 1000) + ttlSeconds,
  }
  const body = base64UrlEncode(encoder.encode(JSON.stringify(payload)))
  const signature = base64UrlEncode(await hmac(secret, body))
  return `${body}.${signature}`
}

/** Verify a token. Returns the payload, or null for anything not perfectly valid. */
export async function verifySession(
  token: string | undefined | null,
  secret: string,
): Promise<SessionPayload | null> {
  if (!token || !secret) return null
  const parts = token.split('.')
  if (parts.length !== 2) return null
  const [body, signature] = parts

  const expected = base64UrlEncode(await hmac(secret, body))
  if (!timingSafeEqual(signature, expected)) return null

  let payload: SessionPayload
  try {
    payload = JSON.parse(new TextDecoder().decode(base64UrlDecode(body)))
  } catch {
    return null
  }
  if (typeof payload?.exp !== 'number' || payload.exp <= Math.floor(Date.now() / 1000)) {
    return null
  }
  return payload
}

/** Constant-time password check. */
export async function checkPassword(candidate: string, expected: string): Promise<boolean> {
  if (!expected || !candidate) return false
  // Compare digests rather than raw strings so the comparison cost does not
  // depend on where the first mismatched character falls.
  const [a, b] = await Promise.all([hmac(expected, candidate), hmac(expected, expected)])
  return timingSafeEqual(base64UrlEncode(a), base64UrlEncode(b))
}

/**
 * Constant-time check of an `Authorization: Bearer <token>` header.
 *
 * Shared by every bearer-guarded route so none of them drifts back to `!==`,
 * which leaks the shared secret's prefix through comparison timing.
 */
export function bearerMatches(header: string | null, secret: string): boolean {
  // Both sides are trimmed. The header was already, but the secret was not —
  // and it arrives from a hosting panel's environment editor, where a trailing
  // newline or a stray space survives a copy-paste invisibly. The symptom is a
  // flat 401 with no clue attached, on a value that looks identical to the one
  // that was pasted. Trimming here costs nothing and removes a whole class of
  // unexplainable deployment failure.
  const expected = (secret || '').trim()
  if (!expected) return false
  const token = (header || '').replace(/^Bearer\s+/i, '').trim()
  return timingSafeEqual(token, expected)
}

export type AuthConfig = { secret: string; password: string; configured: boolean }

export function authConfig(): AuthConfig {
  const secret = process.env.APP_SECRET || ''
  const password = process.env.DASHBOARD_PASSWORD || ''
  return { secret, password, configured: Boolean(secret && password) }
}

/**
 * Whether an unconfigured deployment should be allowed through.
 *
 * Fails **closed** in production: a missing APP_SECRET must lock the dashboard,
 * never silently reopen it. Local development is allowed through so `npm run dev`
 * does not require secrets, and the middleware logs loudly when it does.
 */
export function allowUnconfigured(): boolean {
  return process.env.NODE_ENV !== 'production'
}
