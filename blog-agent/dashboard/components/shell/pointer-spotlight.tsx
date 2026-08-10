'use client'

import { useEffect } from 'react'

/**
 * Feeds `--mx/--my` to whichever `.spotlight` card the cursor is over.
 *
 * One passive listener for the whole app rather than one per card, and it
 * writes only two custom properties — no React state, so a mouse move never
 * causes a render. Devices without a hover-capable pointer, and anyone who has
 * asked for reduced motion, never get the listener at all.
 */
export function PointerSpotlight() {
  useEffect(() => {
    const canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!canHover || reduced) return

    let frame = 0
    let pending: { el: HTMLElement; x: number; y: number } | null = null

    const flush = () => {
      frame = 0
      if (!pending) return
      const { el, x, y } = pending
      el.style.setProperty('--mx', `${x}px`)
      el.style.setProperty('--my', `${y}px`)
      pending = null
    }

    const onMove = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      const card = target?.closest?.('.spotlight') as HTMLElement | null
      if (!card) return
      const rect = card.getBoundingClientRect()
      pending = { el: card, x: event.clientX - rect.left, y: event.clientY - rect.top }
      if (!frame) frame = requestAnimationFrame(flush)
    }

    window.addEventListener('mousemove', onMove, { passive: true })
    return () => {
      window.removeEventListener('mousemove', onMove)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [])

  return null
}
