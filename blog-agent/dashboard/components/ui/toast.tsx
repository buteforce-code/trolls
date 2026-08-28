'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

type Tone = 'default' | 'error'
interface ToastState { id: number; message: string; tone: Tone }

interface ToastApi {
  toast: (message: string, tone?: Tone) => void
}

const ToastContext = createContext<ToastApi>({ toast: () => {} })

const VISIBLE_MS = 2600
/* An error has to be read, not just noticed. "Could not publish — check the
   server logs" at 2.6s is gone before a phone is even raised, and unlike a
   confirmation there is no way to re-derive what it said from the screen. */
const VISIBLE_ERROR_MS = 7000

/**
 * One toast at a time, centred at the bottom, as in the design.
 *
 * It is an `aria-live` region rather than an alert: these messages confirm an
 * action the operator just took ("Published", "Autopilot paused"), so they
 * should be announced without stealing focus. Errors escalate to `assertive`,
 * because "that failed" arriving quietly is worse than an interruption.
 */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [current, setCurrent] = useState<ToastState | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const nextId = useRef(0)

  const toast = useCallback((message: string, tone: Tone = 'default') => {
    nextId.current += 1
    setCurrent({ id: nextId.current, message, tone })
  }, [])

  useEffect(() => {
    if (!current) return
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => setCurrent(null), current.tone === 'error' ? VISIBLE_ERROR_MS : VISIBLE_MS)
    return () => { if (timer.current) clearTimeout(timer.current) }
  }, [current])

  const api = useMemo(() => ({ toast }), [toast])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live={current?.tone === 'error' ? 'assertive' : 'polite'}
        aria-atomic="true"
        className="sr-only"
      >
        {current?.message}
      </div>
      {/* The visible pill is hidden from assistive tech: the persistent live
          region above already carries the text, and a fresh element mounted
          with its own role would either be announced twice or missed entirely
          depending on the screen reader. */}
      {current && (
        <div className="toast" data-tone={current.tone} key={current.id} aria-hidden="true">
          {current.message}
        </div>
      )}
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  return useContext(ToastContext)
}
