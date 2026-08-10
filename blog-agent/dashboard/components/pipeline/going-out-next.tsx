'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import type { Topic } from '../../lib/types'
import { countdown, untilShort } from '../../lib/format'

interface Props {
  topic: Topic | null
  onFeedback: (topic: Topic) => void
  onPublishNow: (topic: Topic) => void
}

/**
 * The veto window, made literal.
 *
 * A scheduled post publishes itself. The difference between "tomorrow" and a
 * running clock is the difference between a note and a deadline, so this is the
 * one number on the board that ticks every second. Everything else on the page
 * updates on the poll.
 */
export function GoingOutNext({ topic, onFeedback, onPublishNow }: Props) {
  const [, forceTick] = useState(0)

  useEffect(() => {
    if (!topic?.scheduled_for) return
    const timer = setInterval(() => forceTick(n => n + 1), 1000)
    return () => clearInterval(timer)
  }, [topic?.scheduled_for])

  return (
    <section
      className="card card--lav rise"
      style={{ flex: '1 1 330px', minWidth: 300, '--i': 5 } as React.CSSProperties}
      aria-label="Going out next"
    >
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 18 }}>
        <h2 className="section-title" style={{ color: 'var(--lav-ink-2)', fontSize: 'var(--text-lg)' }}>
          Going out next
        </h2>
        <span
          className="chip"
          style={{ background: '#fff', color: 'var(--lav-ink)' }}
        >
          Veto window
        </span>
      </div>

      {!topic ? (
        <p style={{ fontSize: 'var(--text-md)', lineHeight: 1.65, color: '#6A5A9A' }}>
          Nothing is scheduled. The village keeps producing, but every piece waits for you —
          nothing publishes itself.
        </p>
      ) : (
        <>
          <Link
            href={`/topic/${topic.slug}`}
            className="pretty"
            style={{
              display: 'block',
              fontWeight: 600,
              fontSize: 'var(--text-lg)',
              lineHeight: 1.45,
              letterSpacing: '-.01em',
              color: '#241546',
              marginBottom: 20,
            }}
          >
            {topic.title}
          </Link>

          <div className="row gap-14" style={{ alignItems: 'flex-end', marginBottom: 6 }}>
            <span
              className="stat-value display"
              style={{ fontSize: 40, color: 'var(--lav-ink)' }}
              aria-label={`Publishes ${untilShort(topic.scheduled_for)}`}
            >
              {countdown(topic.scheduled_for)}
            </span>
            <span className="t-sm" style={{ color: '#7A6AA8', paddingBottom: 5 }}>
              until it publishes itself
            </span>
          </div>

          <p className="t-base" style={{ color: '#7A6AA8', marginBottom: 22 }}>
            Goes {untilShort(topic.scheduled_for)}
          </p>

          <div className="stack gap-10">
            <button type="button" className="btn btn--lav" onClick={() => onPublishNow(topic)}>
              Publish it now
            </button>
            <div className="row gap-10">
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                style={{ flex: 1 }}
                onClick={() => onFeedback(topic)}
              >
                Send feedback
              </button>
              <Link href={`/topic/${topic.slug}`} className="btn btn--ghost btn--sm" style={{ flex: 1 }}>
                Open
              </Link>
            </div>
          </div>
        </>
      )}
    </section>
  )
}
