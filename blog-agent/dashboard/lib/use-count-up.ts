'use client'

import { useEffect, useRef, useState } from 'react'

const DURATION_MS = 900

/**
 * Counts a headline number up from zero on first paint.
 *
 * Two rules keep this from becoming an annoyance:
 *   - it runs once, on mount. Later changes (a poll returning a new count) snap
 *     to the new value, because re-animating on every 3-second poll would make
 *     the board look permanently unstable.
 *   - it is skipped entirely under `prefers-reduced-motion`, which returns the
 *     real number immediately.
 */
export function useCountUp(target: number): number {
  const [value, setValue] = useState(() => target)
  const hasAnimated = useRef(false)
  const frame = useRef<number>(0)

  useEffect(() => {
    if (hasAnimated.current) {
      setValue(target)
      return
    }
    hasAnimated.current = true

    const reduced = typeof window !== 'undefined'
      && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduced || target <= 0) {
      setValue(target)
      return
    }

    const start = performance.now()
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / DURATION_MS)
      // Cubic ease-out: fast enough to feel instant, slow enough at the end to
      // let the final digit be read rather than guessed.
      setValue(Math.round(target * (1 - Math.pow(1 - p, 3))))
      if (p < 1) frame.current = requestAnimationFrame(step)
    }
    frame.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame.current)
  }, [target])

  return value
}
