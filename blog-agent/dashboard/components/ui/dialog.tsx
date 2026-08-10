'use client'

import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

interface DialogProps {
  open: boolean
  onClose: () => void
  title: string
  /** Sub-heading under the title. Also becomes the dialog's description. */
  description?: React.ReactNode
  children?: React.ReactNode
  footer?: React.ReactNode
}

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * A modal that behaves like one.
 *
 * The previous dialog in this app was a styled div: no focus management, no
 * Escape, no `role`, and the page behind it stayed scrollable and tabbable. A
 * keyboard operator could tab straight out of "delete this topic" into the
 * board underneath and press Enter on something else. So this one:
 *
 *   - moves focus in on open and restores it to the trigger on close,
 *   - traps Tab inside the panel,
 *   - closes on Escape and on backdrop click but never on a click that merely
 *     *ended* on the backdrop after starting inside (a text drag-select),
 *   - locks body scroll while open,
 *   - marks the app shell `inert`, which is the half a Tab-trap alone does not
 *     cover: a screen reader's browse cursor moves by arrow key, not by Tab,
 *     and would otherwise walk straight into the board behind the modal,
 *   - announces itself as `role="dialog" aria-modal` with the title and
 *     description wired to it.
 *
 * It renders through a portal on `document.body` so that marking the shell
 * inert cannot also silence the dialog sitting inside it.
 */
export function Dialog({ open, onClose, title, description, children, footer }: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const restoreTo = useRef<HTMLElement | null>(null)
  const pointerDownInside = useRef(false)
  const titleId = useId()
  const descId = useId()
  const [mounted, setMounted] = useState(false)

  // Portals need a DOM target, which does not exist during the server render.
  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    if (!open) return

    restoreTo.current = document.activeElement as HTMLElement | null
    const panel = panelRef.current
    const first = panel?.querySelector<HTMLElement>(FOCUSABLE)
    ;(first ?? panel)?.focus()

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const shell = document.querySelector<HTMLElement>('.shell')
    shell?.setAttribute('inert', '')

    return () => {
      document.body.style.overflow = previousOverflow
      shell?.removeAttribute('inert')
      restoreTo.current?.focus?.()
    }
  }, [open])

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onClose()
        return
      }
      if (event.key !== 'Tab') return

      const nodes = Array.from(panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])
        .filter(el => el.offsetParent !== null)
      if (nodes.length === 0) return

      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      const active = document.activeElement

      if (event.shiftKey && (active === first || active === panelRef.current)) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    },
    [onClose],
  )

  if (!open || !mounted) return null

  return createPortal(
    <div
      className="backdrop"
      onPointerDown={e => { pointerDownInside.current = e.target !== e.currentTarget }}
      onClick={e => {
        if (e.target === e.currentTarget && !pointerDownInside.current) onClose()
        pointerDownInside.current = false
      }}
    >
      <div
        ref={panelRef}
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        onKeyDown={onKeyDown}
      >
        <h2 id={titleId} className="dialog-title">{title}</h2>
        {description && <div id={descId} className="dialog-body">{description}</div>}
        {children}
        {footer && <div className="dialog-actions">{footer}</div>}
      </div>
    </div>,
    document.body,
  )
}
