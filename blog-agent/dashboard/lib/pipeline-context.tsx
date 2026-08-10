'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { AutopilotState, Topic } from './types'
import { countByLane, statusMeta, type StatusGroup } from './status'

interface PipelineValue {
  topics: Topic[]
  autopilot: AutopilotState | null
  counts: Record<StatusGroup, number>
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  /** Optimistic local edits, so the board reacts before the poll catches up. */
  removeTopic: (slug: string) => void
  upsertTopic: (topic: Topic) => void
}

const EMPTY_COUNTS: Record<StatusGroup, number> = {
  attention: 0, scheduled: 0, progress: 0, queued: 0, published: 0,
}

const PipelineContext = createContext<PipelineValue>({
  topics: [], autopilot: null, counts: EMPTY_COUNTS, loading: true, error: null,
  refresh: async () => {}, removeTopic: () => {}, upsertTopic: () => {},
})

const ACTIVE_MS = 3000
const IDLE_MS = 10_000

/**
 * One source of pipeline truth for the whole shell.
 *
 * The sidebar counts, the board, the stat cards and the autopilot strip all
 * describe the same list. Fetching it once here rather than in each component
 * removes three duplicate requests per poll and, more importantly, removes the
 * window where the sidebar said "2 need review" and the board showed three.
 *
 * Polling speeds up to 3s only while an agent is actually running, backs off to
 * 10s otherwise, and stops completely while the tab is hidden.
 */
export function PipelineProvider({ children }: { children: React.ReactNode }) {
  const [topics, setTopics] = useState<Topic[]>([])
  const [autopilot, setAutopilot] = useState<AutopilotState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const cancelled = useRef(false)

  const load = useCallback(async (): Promise<Topic[]> => {
    try {
      const res = await fetch('/api/topics', { headers: { accept: 'application/json' } })
      if (res.status === 401) { window.location.reload(); return [] }
      if (!res.ok) throw new Error(`topics: ${res.status}`)
      const json = await res.json()
      const next: Topic[] = json.topics ?? []
      if (!cancelled.current) { setTopics(next); setError(null) }

      // Autopilot is a separate, cheaper read and must never block the board.
      fetch('/api/autopilot', { headers: { accept: 'application/json' } })
        .then(r => (r.ok ? r.json() : null))
        .then(s => { if (s && !cancelled.current) setAutopilot(s) })
        .catch(() => {})

      return next
    } catch (err: unknown) {
      if (!cancelled.current) setError(err instanceof Error ? err.message : 'could not load topics')
      return []
    } finally {
      if (!cancelled.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    cancelled.current = false

    const loop = async () => {
      if (cancelled.current) return
      if (document.visibilityState === 'hidden') {
        timer.current = setTimeout(loop, IDLE_MS)
        return
      }
      const fresh = await load()
      if (cancelled.current) return
      const busy = fresh.some(t => statusMeta(t.status).live || t.status === 'queued')
      timer.current = setTimeout(loop, busy ? ACTIVE_MS : IDLE_MS)
    }

    const onVisible = () => { if (document.visibilityState === 'visible') loop() }
    document.addEventListener('visibilitychange', onVisible)
    loop()

    return () => {
      cancelled.current = true
      document.removeEventListener('visibilitychange', onVisible)
      if (timer.current) clearTimeout(timer.current)
    }
  }, [load])

  const removeTopic = useCallback((slug: string) => {
    setTopics(prev => prev.filter(t => t.slug !== slug))
  }, [])

  const upsertTopic = useCallback((topic: Topic) => {
    setTopics(prev => [topic, ...prev.filter(t => t.slug !== topic.slug)])
  }, [])

  const refresh = useCallback(async () => { await load() }, [load])

  const value = useMemo<PipelineValue>(() => ({
    topics,
    autopilot,
    counts: countByLane(topics),
    loading,
    error,
    refresh,
    removeTopic,
    upsertTopic,
  }), [topics, autopilot, loading, error, refresh, removeTopic, upsertTopic])

  return <PipelineContext.Provider value={value}>{children}</PipelineContext.Provider>
}

export function usePipeline(): PipelineValue {
  return useContext(PipelineContext)
}
