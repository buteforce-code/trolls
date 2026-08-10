'use client'

import { useEffect, useRef } from 'react'

interface LiveRailProps {
  lines: readonly string[]
  live: boolean
  children: React.ReactNode
}

/**
 * The live log and the action stack.
 *
 * The log auto-scrolls only when the operator is already at the bottom. Forcing
 * a scroll while someone is reading a stack trace higher up is the fastest way
 * to make a debugging surface useless.
 */
export function LiveRail({ lines, live, children }: LiveRailProps) {
  const logRef = useRef<HTMLDivElement>(null)
  const pinned = useRef(true)

  useEffect(() => {
    const el = logRef.current
    if (el && pinned.current) el.scrollTop = el.scrollHeight
  }, [lines])

  function onScroll() {
    const el = logRef.current
    if (!el) return
    pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40
  }

  return (
    <aside
      className="rise"
      style={{ position: 'sticky', top: 30, flex: '1 1 320px', maxWidth: 400, minWidth: 300, '--i': 3 } as React.CSSProperties}
      aria-label="Run log and actions"
    >
      <div className="card card--tight">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 14 }}>
          <h2 className="section-title" style={{ fontSize: 16 }}>Live log</h2>
          <span
            className="row gap-8 t-sm"
            style={{ fontWeight: 600, color: live ? 'var(--teal-ink)' : 'var(--ink-mute)' }}
          >
            <span
              className={`dot${live ? ' pulse pulse--fast' : ''}`}
              style={{
                width: 7, height: 7,
                background: live ? 'var(--teal)' : 'var(--grey-dot)',
                color: live ? 'var(--teal)' : 'var(--grey-dot)',
              }}
              aria-hidden="true"
            />
            {live ? 'Live' : 'Idle'}
          </span>
        </div>

        <div
          ref={logRef}
          onScroll={onScroll}
          className="log scroller"
          style={{ height: 290 }}
          role="log"
          aria-live="off"
          aria-label="Worker output"
          tabIndex={0}
        >
          {lines.length === 0 ? (
            <p style={{ color: 'var(--ink-mute)' }}>
              No worker output for this topic yet. Logs appear once a job runs on this server.
            </p>
          ) : (
            lines.map((line, i) => (
              <div key={i} style={{ color: toneOf(line) }}>{line}</div>
            ))
          )}
        </div>

        <div className="stack gap-10" style={{ marginTop: 16 }}>{children}</div>
      </div>
    </aside>
  )
}

/**
 * Colour by severity, read from the line itself. The Python side already tags
 * stderr, and the words that matter in a failure are consistent enough to be
 * worth catching — a red line in a wall of grey is the fastest possible triage.
 */
function toneOf(line: string): string {
  const lower = line.toLowerCase()
  if (lower.includes('[stderr]') || lower.includes('error') || lower.includes('failed') || lower.includes('traceback')) {
    return 'var(--rose-ink)'
  }
  if (lower.includes('warn') || lower.includes('retry') || lower.includes('rejected')) return 'var(--amber-ink)'
  if (lower.includes('passed') || lower.includes('published') || lower.includes('approved')) return 'var(--teal-ink)'
  return 'var(--ink-3)'
}
