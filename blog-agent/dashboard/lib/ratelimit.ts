/**
 * In-process fixed-window rate limiter.
 *
 * Scope and honesty about it: this is per-instance memory. On a single Render
 * web service that is the whole deployment, so it is effective today. It is not
 * a distributed limiter — if this ever scales to multiple instances, or moves to
 * a serverless platform that spins up many isolates, move the counter to
 * Postgres or Redis. It also resets on redeploy, which is acceptable for the
 * two things it protects (login brute force, view-count flooding) and would not
 * be acceptable for anything billing-related.
 */

type Window = { count: number; resetAt: number }

const buckets = new Map<string, Window>()

// Bound the map so a flood of unique keys cannot grow it without limit — that
// would turn the rate limiter itself into the memory-exhaustion vector on a
// 512 MB instance.
const MAX_TRACKED_KEYS = 10_000

function sweep(now: number): void {
  for (const [key, window] of buckets) {
    if (window.resetAt <= now) buckets.delete(key)
  }
}

export type RateLimitResult = { allowed: boolean; remaining: number; retryAfterSeconds: number }

export function rateLimit(key: string, limit: number, windowSeconds: number): RateLimitResult {
  const now = Date.now()
  const existing = buckets.get(key)

  if (!existing || existing.resetAt <= now) {
    if (buckets.size >= MAX_TRACKED_KEYS) sweep(now)
    if (buckets.size >= MAX_TRACKED_KEYS) {
      // Still full after a sweep: fail open rather than lock everyone out. The
      // limiter is a safety net, not an access control — middleware.ts is.
      return { allowed: true, remaining: 0, retryAfterSeconds: 0 }
    }
    buckets.set(key, { count: 1, resetAt: now + windowSeconds * 1000 })
    return { allowed: true, remaining: limit - 1, retryAfterSeconds: 0 }
  }

  existing.count += 1
  const retryAfterSeconds = Math.max(1, Math.ceil((existing.resetAt - now) / 1000))
  if (existing.count > limit) {
    return { allowed: false, remaining: 0, retryAfterSeconds }
  }
  return { allowed: true, remaining: limit - existing.count, retryAfterSeconds: 0 }
}

/**
 * Best-effort client identity for rate limiting.
 *
 * `x-forwarded-for` is spoofable in general, but Render terminates TLS and
 * rewrites it, so the left-most entry is trustworthy behind that proxy. Falls
 * back to a constant so a missing header degrades to a global limit rather than
 * to no limit at all.
 */
export function clientKey(request: Request, prefix: string): string {
  const forwarded = request.headers.get('x-forwarded-for') || ''
  const ip = forwarded.split(',')[0]?.trim() || request.headers.get('x-real-ip') || 'unknown'
  return `${prefix}:${ip}`
}
