'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

interface PollOptions {
  /** Interval used when `isBusy` says work is in flight. */
  activeMs?: number
  /** Interval used when nothing is moving. */
  idleMs?: number
  enabled?: boolean
}

export interface PollResult<T> {
  data: T | null
  error: string | null
  loading: boolean
  /** Fetch immediately, outside the schedule — used after a mutation. */
  refresh: () => Promise<void>
}

/**
 * Adaptive polling for a JSON endpoint.
 *
 * Three things this does that a bare `setInterval` does not:
 *   - it schedules the *next* fetch after the previous one lands, so a slow
 *     response can never stack up a queue of overlapping requests;
 *   - it backs off from 3s to 10s when nothing in the payload is moving, which
 *     is most of the time — the pipeline is idle far more than it is running;
 *   - it stops entirely while the tab is hidden. A dashboard left open in a
 *     background tab overnight was previously worth ~10,000 pointless queries.
 */
export function usePoll<T>(
  url: string,
  isBusy: (data: T) => boolean,
  { activeMs = 3000, idleMs = 10_000, enabled = true }: PollOptions = {},
): PollResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const cancelled = useRef(false)
  const busyRef = useRef(isBusy)
  busyRef.current = isBusy

  const fetchOnce = useCallback(async (): Promise<T | null> => {
    try {
      const res = await fetch(url, { headers: { accept: 'application/json' } })
      if (!res.ok) {
        // A 401 means the session lapsed while the tab sat open. Reloading
        // lets the middleware bounce to /login rather than leaving a dashboard
        // that silently stops updating.
        if (res.status === 401) { window.location.reload(); return null }
        throw new Error(`${res.status}`)
      }
      const json = (await res.json()) as T
      if (cancelled.current) return null
      setData(json)
      setError(null)
      return json
    } catch (err: unknown) {
      if (!cancelled.current) setError(err instanceof Error ? err.message : 'request failed')
      return null
    } finally {
      if (!cancelled.current) setLoading(false)
    }
  }, [url])

  useEffect(() => {
    if (!enabled) { setLoading(false); return }
    cancelled.current = false

    const schedule = (ms: number) => {
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(loop, ms)
    }

    const loop = async () => {
      if (cancelled.current) return
      if (document.visibilityState === 'hidden') { schedule(idleMs); return }
      const fresh = await fetchOnce()
      if (cancelled.current) return
      schedule(fresh && busyRef.current(fresh) ? activeMs : idleMs)
    }

    // Coming back to the tab should show current data, not data from an hour ago.
    const onVisible = () => { if (document.visibilityState === 'visible') loop() }
    document.addEventListener('visibilitychange', onVisible)

    loop()
    return () => {
      cancelled.current = true
      document.removeEventListener('visibilitychange', onVisible)
      if (timer.current) clearTimeout(timer.current)
    }
  }, [enabled, fetchOnce, activeMs, idleMs])

  const refresh = useCallback(async () => { await fetchOnce() }, [fetchOnce])

  return { data, error, loading, refresh }
}
