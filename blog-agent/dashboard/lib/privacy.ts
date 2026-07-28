/**
 * Privacy helpers for view tracking (DPDP Act 2023 / GDPR).
 *
 * `blog_views` stores what a visitor read and when. Under both India's DPDP Act
 * and the GDPR that is personal data, and until now it was kept raw and forever:
 * a full user-agent string and a caller-supplied `session_id`, with no retention
 * limit and no way to honour a deletion request.
 *
 * Three changes, all enforced in code rather than promised in a policy page:
 *
 * 1. **Pseudonymisation.** The session id is replaced by a keyed SHA-256 digest.
 *    Unique-visitor counting still works; the stored value no longer identifies
 *    a device and cannot be reversed without VIEW_HASH_SALT.
 * 2. **Minimisation.** The user-agent is reduced to a coarse client family
 *    ("Chrome", "Safari", "bot"). That is all the analytics page ever used it
 *    for, and it drops the high-entropy fingerprint.
 * 3. **Retention.** Every row is written with an `expires_at`, so the deadline
 *    is a queryable database fact. `purge_expired_views()` deletes past it.
 *
 * Set VIEW_HASH_SALT to a long random string. Rotating it deliberately breaks
 * continuity of the pseudonyms — which is the correct behaviour, not a bug.
 */

export const DEFAULT_RETENTION_DAYS = 90

export function retentionDays(): number {
  const raw = Number(process.env.VIEW_RETENTION_DAYS || DEFAULT_RETENTION_DAYS)
  if (!Number.isFinite(raw) || raw <= 0) return DEFAULT_RETENTION_DAYS
  // Capped: an unbounded retention window is exactly what the DPDP storage
  // limitation principle prohibits, so config cannot opt out of having a limit.
  return Math.min(raw, 400)
}

export function expiresAt(from: Date = new Date()): string {
  const out = new Date(from)
  out.setUTCDate(out.getUTCDate() + retentionDays())
  return out.toISOString()
}

/** Keyed, non-reversible digest of a visitor session id. */
export async function pseudonymise(sessionId: string | null): Promise<string | null> {
  if (!sessionId) return null
  const salt = process.env.VIEW_HASH_SALT || ''
  if (!salt) {
    // Without a salt a plain hash of a short id is trivially rainbow-tabled, so
    // storing nothing is strictly more private than storing a weak pseudonym.
    console.warn('[privacy] VIEW_HASH_SALT unset — dropping session ids rather than storing weak hashes.')
    return null
  }
  const bytes = new TextEncoder().encode(`${salt}:${sessionId}`)
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return Array.from(new Uint8Array(digest))
    .slice(0, 16)
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
}

const CLIENT_FAMILIES: [RegExp, string][] = [
  [/bot|crawler|spider|crawling|headless/i, 'bot'],
  [/edg\//i, 'Edge'],
  [/opr\/|opera/i, 'Opera'],
  [/chrome|crios/i, 'Chrome'],
  [/firefox|fxios/i, 'Firefox'],
  [/safari/i, 'Safari'],
]

/** Reduce a user-agent to a coarse family. Returns null when unrecognised. */
export function clientFamily(userAgent: string | null): string | null {
  if (!userAgent) return null
  for (const [pattern, name] of CLIENT_FAMILIES) {
    if (pattern.test(userAgent)) return name
  }
  return 'other'
}

/**
 * Keep only the origin + path of a referrer.
 *
 * Query strings routinely carry campaign ids, click ids and occasionally
 * personal data pasted into a URL. None of it is used by the stats page.
 */
export function safeReferrer(referrer: string | null): string | null {
  if (!referrer) return null
  try {
    const url = new URL(referrer)
    return `${url.origin}${url.pathname}`.slice(0, 256)
  } catch {
    return null
  }
}
