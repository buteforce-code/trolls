'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { usePipeline } from '../../lib/pipeline-context'
import { statusMeta, substatus } from '../../lib/status'
import { untilShort } from '../../lib/format'
import type { Topic } from '../../lib/types'
import { BellIcon } from '../ui/icons'

/** Inside this window a scheduled post is close enough to publishing to be news. */
const IMMINENT_MS = 24 * 60 * 60 * 1000

/** Lavender is the machine's own intent, rose is "a human must decide" — the
 *  palette's meaning, not a decoration. See app/styles/tokens.css. */
const TONE: Record<'lav' | 'rose', string> = {
  lav: 'var(--lav-deep)',
  rose: 'var(--rose)',
}

type Tone = keyof typeof TONE

interface Item {
  slug: string
  title: string
  headline: string
  detail: string
  tone: Tone
  /** Lower sorts first. */
  rank: number
}

/**
 * Turn the board into the short list of things actually waiting on a human.
 *
 * Derived from the topics the shell already polls rather than a new endpoint —
 * a second source would be a second thing that can disagree with the sidebar
 * counts, and those counts are the reason the operator clicked.
 *
 * Order is by urgency, not recency. A post publishing in three hours outranks a
 * failure from yesterday, because only one of them has a deadline.
 */
function buildItems(topics: readonly Topic[]): Item[] {
  const now = Date.now()
  const items: Item[] = []

  for (const topic of topics) {
    const meta = statusMeta(topic.status)

    if (topic.status === 'scheduled' && topic.scheduled_for) {
      const due = new Date(topic.scheduled_for).getTime()
      if (!Number.isNaN(due) && due - now <= IMMINENT_MS) {
        items.push({
          slug: topic.slug,
          title: topic.title,
          headline: `Publishes ${untilShort(topic.scheduled_for)}`,
          detail: 'Goes out on its own unless you step in',
          tone: 'lav',
          rank: Math.max(0, due - now),
        })
      }
      continue
    }

    if (meta.group === 'attention') {
      items.push({
        slug: topic.slug,
        title: topic.title,
        headline: topic.status === 'failed' ? 'Failed' : meta.label,
        detail: substatus(topic.status, topic.scheduled_for),
        tone: 'rose',
        // After every imminent publish, newest first.
        rank: IMMINENT_MS + (now - new Date(topic.updated_at).getTime()),
      })
    }
  }

  return items.sort((a, b) => a.rank - b.rank)
}

/**
 * The bell, and the panel it opens.
 *
 * This was a bare `<Link>` to the review lane. Because every lane rendered the
 * same analytics header, following it changed almost nothing on screen and the
 * bell read as broken.
 *
 * A popover, not a `Dialog`: that component locks body scroll and marks the
 * shell `inert`, which is right for "delete this topic" and wrong for a
 * dropdown you glance at. The Escape / click-outside / focus-restore behaviour
 * is modelled on it at the lighter weight a non-modal needs.
 */
export function NotificationBell() {
  const { topics } = usePipeline()
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const items = useMemo(() => buildItems(topics), [topics])

  const close = useCallback((restoreFocus = true) => {
    setOpen(false)
    if (restoreFocus) buttonRef.current?.focus()
  }, [])

  useEffect(() => {
    if (!open) return

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); close() }
    }
    // `pointerdown`, not `click`: a click that begins inside the panel and ends
    // outside it (a drag-select over a title) must not count as dismissal.
    const onPointerDown = (e: PointerEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) close(false)
    }

    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointerDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointerDown)
    }
  }, [open, close])

  const count = items.length
  const label = count
    ? `Notifications, ${count} waiting on you`
    : 'Notifications, nothing waiting on you'

  return (
    <div className="notif-wrap" ref={wrapRef}>
      <button
        ref={buttonRef}
        type="button"
        className="icon-btn"
        aria-label={label}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen(o => !o)}
      >
        <BellIcon />
        {count > 0 && <span className="icon-btn-badge" aria-hidden="true">{count}</span>}
      </button>
      {/* The badge is `aria-hidden` and the button's own name only updates when
          the button is re-read, so a count that changed under a poll was silent.
          This announces the change itself, which is the part that matters. */}
      <span className="sr-only" aria-live="polite">{label}</span>

      {open && (
        <div className="notif-panel" role="dialog" aria-label="Notifications">
          <div className="notif-head">
            <span className="notif-title">Needs you</span>
            <span className="t-sm muted">{count === 0 ? 'all clear' : `${count} item${count === 1 ? '' : 's'}`}</span>
          </div>

          {count === 0 ? (
            <p className="notif-empty">
              Nothing is waiting on your decision. Scheduled posts ship unless you step in.
            </p>
          ) : (
            <ul className="notif-list">
              {items.slice(0, 8).map(item => (
                <li key={item.slug}>
                  <Link href={`/topic/${item.slug}`} className="notif-item" onClick={() => close(false)}>
                    <span
                      className="dot dot--lg"
                      style={{ color: TONE[item.tone] }}
                      aria-hidden="true"
                    />
                    <span className="notif-item-text">
                      <span className="notif-item-head">{item.headline}</span>
                      <span className="notif-item-title">{item.title}</span>
                      <span className="notif-item-detail">{item.detail}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          <Link href="/?lane=attention" className="notif-foot" onClick={() => close(false)}>
            Open the review lane
            <span aria-hidden="true">→</span>
          </Link>
        </div>
      )}
    </div>
  )
}
