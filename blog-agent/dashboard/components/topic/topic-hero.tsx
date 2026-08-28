'use client'

import { useEffect, useState } from 'react'
import type { BlogPost, Topic } from '../../lib/types'
import { countdown } from '../../lib/format'
import { STAGES, classifyFailure, stageStates, statusMeta, substatus } from '../../lib/status'
import { StatusChip, Tag } from '../ui/chip'

/**
 * Which stage a failed run died at.
 *
 * The pipeline does not persist a stage index on failure, so it is inferred
 * from the furthest artefact that made it to disk. That is a guess, but it is a
 * guess made from evidence — and it is the difference between "it broke" and
 * "it broke after research, so the research is worth keeping".
 */
function failedStage(post: BlogPost | null): number {
  if (post?.mdx_final) return 4
  if (post?.mdx_draft) return 3
  if (post?.research_json) return 1
  return 0
}

const STAGE_TONE = {
  done:    { bg: 'var(--teal-tint)', dot: 'var(--teal)',      ink: 'var(--teal-ink)' },
  active:  { bg: 'var(--lav-tint)',  dot: 'var(--lav-deep)',  ink: 'var(--lav-ink)' },
  pending: { bg: 'var(--bg)',        dot: '#D5D2E2',          ink: 'var(--ink-mute)' },
  failed:  { bg: 'var(--rose-tint)', dot: 'var(--rose)',      ink: 'var(--rose-ink)' },
} as const

export function TopicHero({ topic, post }: { topic: Topic; post: BlogPost | null }) {
  const states = stageStates(topic.status, failedStage(post))
  const meta = statusMeta(topic.status)

  return (
    <section className="card rise mb-22">
      <StatusChip status={topic.status} large />

      <h1
        className="display pretty"
        style={{ margin: '16px 0 8px', fontSize: 29, fontWeight: 700, letterSpacing: '-.03em', lineHeight: 1.24 }}
      >
        {topic.title}
      </h1>

      {/* Polite, because this line is where a run's progress actually shows up.
          The page re-polls every 4s and the status changes under the reader; a
          screen-reader operator watching a topic was previously never told the
          run had failed, or scheduled, or finished. It is a short single line,
          so announcing it in full costs nothing. */}
      <p className="t-base" style={{ color: 'var(--ink-mute)', marginBottom: 18 }} aria-live="polite">
        /{topic.slug} · {substatus(topic.status, topic.scheduled_for, null, post?.last_error)}
      </p>

      {(topic.tags?.length ?? 0) > 0 && (
        <div className="row wrap gap-6 mb-22">
          {topic.tags!.map(tag => <Tag key={tag}>{tag}</Tag>)}
        </div>
      )}

      <ol className="row wrap gap-6 mb-22" style={{ listStyle: 'none' }} aria-label="Pipeline progress">
        {STAGES.map((stage, i) => {
          const tone = STAGE_TONE[states[i]]
          return (
            <li
              key={stage}
              className="row gap-8"
              style={{ padding: '8px 15px', borderRadius: 'var(--r-pill)', background: tone.bg }}
            >
              <span
                className={`dot${states[i] === 'active' ? ' pulse pulse--fast' : ''}`}
                style={{ width: 7, height: 7, background: tone.dot, color: tone.dot }}
                aria-hidden="true"
              />
              <span className="t-sm" style={{ fontWeight: 500, color: tone.ink }}>{stage}</span>
              <span className="sr-only">{states[i]}</span>
            </li>
          )
        })}
      </ol>

      <StatusBanner topic={topic} post={post} live={meta.live} />
    </section>
  )
}

function StatusBanner({ topic, post, live }: { topic: Topic; post: BlogPost | null; live: boolean }) {
  const [, tick] = useState(0)
  const scheduled = topic.status === 'scheduled' && topic.scheduled_for

  useEffect(() => {
    if (!scheduled) return
    const timer = setInterval(() => tick(n => n + 1), 1000)
    return () => clearInterval(timer)
  }, [scheduled])

  if (scheduled) {
    return (
      <div className="notice notice--lav">
        <span style={{ flex: 1, minWidth: 200 }}>
          Scheduled. This publishes itself unless you act — your veto window.
        </span>
        <span className="display tnum" style={{ fontWeight: 700, fontSize: 16, color: 'var(--lav-ink)' }}>
          {countdown(topic.scheduled_for)}
        </span>
      </div>
    )
  }

  if (topic.status === 'failed') {
    return <FailureBanner lastError={post?.last_error} />
  }

  if (topic.status === 'verifying_research' || topic.status === 'verifying_draft') {
    return (
      <div className="notice notice--rose">
        <span style={{ flex: 1, minWidth: 200 }}>
          Waiting at a review gate for your decision. Nothing moves until you call it.
        </span>
      </div>
    )
  }

  if (live) {
    return (
      <div className="notice notice--teal">
        <span className="dot dot--lg pulse" style={{ background: 'var(--teal)', color: 'var(--teal)' }} aria-hidden="true" />
        <span style={{ flex: 1, minWidth: 200 }}>
          Running in the background — {substatus(topic.status).toLowerCase()}. A few minutes.
        </span>
      </div>
    )
  }

  if (topic.status === 'published') {
    return (
      <div className="notice notice--grey">
        <span style={{ flex: 1, minWidth: 200 }}>Published and live. Archived.</span>
      </div>
    )
  }

  return (
    <div className="notice notice--grey">
      <span style={{ flex: 1, minWidth: 200 }}>Queued and waiting its turn. Nothing to do.</span>
    </div>
  )
}

/**
 * What a failed run tells the operator.
 *
 * Two failures look identical in the database and are nothing alike in what they
 * ask of a person. A crashed stage is worth retrying. A provider refusing on a
 * spent balance is not — on 2026-08-27 that refusal killed eight topics in a row,
 * and the banner said "A stage crashed" all eight times while the only useful
 * action was topping up an account. So the blocked case gets its own colour, its
 * own next step, and a link straight to the fix; and either way the provider's
 * own words stay one click away, because "open a SQL console to find out it was a
 * 402" is not an acceptable answer to "why did this stop".
 */
function FailureBanner({ lastError }: { lastError?: string | null }) {
  const failure = classifyFailure(lastError)
  const blocked = failure.kind === 'blocked'

  return (
    <div className={blocked ? 'notice notice--amber' : 'notice notice--rose'} style={{ alignItems: 'flex-start' }}>
      <div style={{ flex: 1, minWidth: 200, display: 'grid', gap: 8 }}>
        <span style={{ fontWeight: 600 }}>{failure.headline}</span>

        {failure.action && (
          <span className="t-sm">
            {failure.action}
            {failure.href && (
              <>
                {' '}
                <a href={failure.href} target="_blank" rel="noreferrer" style={{ fontWeight: 600 }}>
                  Open the top-up page ↗
                </a>
              </>
            )}
          </span>
        )}

        {blocked && (
          <span className="t-sm" style={{ opacity: 0.85 }}>
            The research for this topic is already stored and paid for. Once the account is
            funded, <code>python run.py --resume-failed</code> re-runs the writer from it
            rather than researching again.
          </span>
        )}

        {/* The raw provider text, collapsed. Nobody wants a wall of JSON in the
            banner, and the one person debugging it needs every character of it. */}
        {failure.raw && (blocked || failure.raw !== failure.headline) && (
          <details className="t-sm">
            <summary style={{ cursor: 'pointer' }}>Show the exact error</summary>
            <pre
              style={{
                whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginTop: 8,
                maxHeight: 220, overflowY: 'auto', fontSize: 12, lineHeight: 1.5,
              }}
            >
              {failure.raw}
            </pre>
          </details>
        )}
      </div>
    </div>
  )
}
