'use client'

import { use, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import type { AgentEvent, AgentRun, BlogPost, Topic } from '../../../lib/types'
import { num } from '../../../lib/format'
import { statusMeta } from '../../../lib/status'
import { useToast } from '../../../components/ui/toast'
import { ArrowLeftIcon } from '../../../components/ui/icons'
import { EmptyState } from '../../../components/ui/page-header'
import { Dialog } from '../../../components/ui/dialog'
import { CopyButton } from '../../../components/ui/copy-button'
import { Tabs, TabPanel, type TabDef } from '../../../components/topic/tabs'
import { TopicHero } from '../../../components/topic/topic-hero'
import {
  DraftPanel, MonitorPanel, SchemaPanel, parseJson, type Audit, type Digest,
} from '../../../components/topic/panels'
import { SocialPanel, type SocialKit } from '../../../components/topic/social-panel'
import { GeoPanel } from '../../../components/topic/geo-panel'
import { LiveRail } from '../../../components/topic/live-rail'

const TABS: readonly TabDef[] = [
  { id: 'monitor', label: 'Monitor' },
  { id: 'draft',   label: 'Draft' },
  { id: 'social',  label: 'Social kit' },
  { id: 'schema',  label: 'Schema' },
  { id: 'geo',     label: 'GEO gate' },
  { id: 'video',   label: 'Video kit' },
]

interface VideoKit {
  props: Record<string, unknown>
  commands: { studio: string; vertical: string; landscape: string }
}

export default function TopicPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params)
  const router = useRouter()
  const { toast } = useToast()

  const [topic, setTopic] = useState<Topic | null>(null)
  const [post, setPost] = useState<BlogPost | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [logLines, setLogLines] = useState<string[]>([])
  const [video, setVideo] = useState<VideoKit | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState('monitor')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [feedback, setFeedback] = useState('')

  const logCursor = useRef(0)
  const statusRef = useRef<string | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/topic/${slug}`, { headers: { accept: 'application/json' } })
      if (res.status === 404) { setNotFound(true); return }
      if (res.status === 401) { window.location.reload(); return }
      if (!res.ok) return
      const data = await res.json()
      setTopic(data.topic as Topic)
      setPost((data.post ?? null) as BlogPost | null)
    } finally {
      setLoading(false)
    }
  }, [slug])

  useEffect(() => { statusRef.current = topic?.status ?? null }, [topic?.status])

  // Only poll the record while an agent could be changing it. A published topic
  // is immutable and does not deserve a request every four seconds.
  useEffect(() => {
    load()
    const timer = setInterval(() => {
      const status = statusRef.current
      if (status && (statusMeta(status).live || status === 'queued')) load()
    }, 4000)
    return () => clearInterval(timer)
  }, [load])

  // Worker logs are file-backed and exist for finished jobs too, so they load
  // once regardless of state and keep tailing only while something is running.
  useEffect(() => {
    let cancelled = false
    const pull = async () => {
      try {
        const res = await fetch(`/api/topic/${slug}/logs?after=${logCursor.current}`)
        if (!res.ok || cancelled) return
        const data = await res.json()
        if (cancelled) return
        if (Array.isArray(data.lines) && data.lines.length > 0) {
          setLogLines(prev => [...prev, ...data.lines].slice(-500))
        }
        if (typeof data.totalBytes === 'number') logCursor.current = data.totalBytes
      } catch { /* the log file simply may not exist */ }
    }
    pull()
    const timer = setInterval(pull, 3000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [slug])

  // The GEO tab reports what the gate actually did, which lives in this topic's
  // most recent run rather than on the post row. Two hops, fetched once.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const runsRes = await fetch('/api/swarm?limit=40')
        if (!runsRes.ok || cancelled) return
        const { runs } = (await runsRes.json()) as { runs: AgentRun[] }
        const mine = runs.find(r => r.topic_slug === slug)
        if (!mine || cancelled) return
        const eventsRes = await fetch(`/api/swarm/${mine.id}`)
        if (!eventsRes.ok || cancelled) return
        const data = (await eventsRes.json()) as { events: AgentEvent[] }
        if (!cancelled) setEvents(data.events ?? [])
      } catch { /* telemetry is optional context, never a blocker */ }
    })()
    return () => { cancelled = true }
  }, [slug])

  useEffect(() => {
    if (tab !== 'video' || video) return
    let cancelled = false
    fetch(`/api/topic/${slug}/video`)
      .then(r => (r.ok ? r.json() : null))
      .then(data => { if (data && !cancelled) setVideo(data as VideoKit) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [tab, slug, video])

  const digest = useMemo(() => parseJson<Digest>(post?.research_json), [post?.research_json])
  const audit = useMemo(() => parseJson<Audit>(post?.audit_json), [post?.audit_json])
  const social = useMemo(() => parseJson<SocialKit>(post?.social_json), [post?.social_json])

  async function act(url: string, body: Record<string, unknown>, success: string) {
    setBusy(true)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        toast(data.error || 'That did not go through', 'error')
        return false
      }
      toast(success)
      // The Python job runs detached, so the row changes a moment later.
      setTimeout(load, 1200)
      return true
    } catch {
      toast('Could not reach the server', 'error')
      return false
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    const ok = await act('/api/delete', { slug }, 'Topic deleted')
    setConfirmDelete(false)
    if (ok) setTimeout(() => router.replace('/'), 900)
  }

  async function sendFeedback() {
    if (!feedback.trim()) return
    const ok = await act('/api/reject', { slug, feedback: feedback.trim() }, 'Sent back for a re-draft')
    if (ok) { setFeedback(''); setFeedbackOpen(false) }
  }

  if (notFound) {
    return (
      <EmptyState
        title="No such topic"
        hint="It may have been deleted while this page was open."
        action={<Link href="/" className="btn btn--lav">Back to the pipeline</Link>}
      />
    )
  }

  if (loading || !topic) {
    return (
      <div aria-busy="true" aria-live="polite">
        <span className="sr-only">Loading the topic</span>
        <div className="card mb-22" style={{ height: 280 }} />
        <div className="card" style={{ height: 420 }} />
      </div>
    )
  }

  const meta = statusMeta(topic.status)
  const wordCount = post?.word_count ?? 0

  return (
    <div className="view-enter">
      <div className="row wrap gap-12 mb-18" style={{ justifyContent: 'space-between' }}>
        <Link href="/" className="btn btn--ghost btn--sm">
          <ArrowLeftIcon />
          Back to pipeline
        </Link>
        <button
          type="button"
          className="btn btn--danger btn--sm"
          onClick={() => setConfirmDelete(true)}
          disabled={busy}
        >
          Delete topic
        </button>
      </div>

      <TopicHero topic={topic} post={post} />

      <div className="row wrap gap-22" style={{ alignItems: 'flex-start' }}>
        <div
          className="card rise"
          style={{ minWidth: 0, flex: '10 1 520px', '--i': 2 } as React.CSSProperties}
        >
          <div className="mb-22">
            <Tabs tabs={TABS} active={tab} onChange={setTab} label="Topic detail" />
          </div>

          <TabPanel id="monitor" active={tab}><MonitorPanel digest={digest} audit={audit} /></TabPanel>
          <TabPanel id="draft" active={tab}><DraftPanel post={post} /></TabPanel>
          <TabPanel id="social" active={tab}><SocialPanel kit={social} /></TabPanel>
          <TabPanel id="schema" active={tab}><SchemaPanel schema={post?.schema_json} /></TabPanel>
          <TabPanel id="geo" active={tab}><GeoPanel events={events} wordCount={wordCount} /></TabPanel>
          <TabPanel id="video" active={tab}><VideoPanel kit={video} slug={slug} /></TabPanel>
        </div>

        <LiveRail lines={logLines} live={meta.live}>
          <ActionStack
            topic={topic}
            post={post}
            busy={busy}
            onApprove={() => act('/api/approve', { slug }, 'Approved — moving on')}
            onFeedback={() => setFeedbackOpen(true)}
            onReset={() => act('/api/reset', { slug }, 'Reset to the review stage')}
            onRerun={() => act('/api/run', { title: topic.title, tags: topic.tags ?? [] }, 'Re-running from research')}
          />
        </LiveRail>
      </div>

      <Dialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title="Delete this topic?"
        description={`“${topic.title}” and its draft, research and social kit are removed. This cannot be undone.`}
        footer={
          <>
            <button type="button" className="btn btn--ghost" onClick={() => setConfirmDelete(false)} disabled={busy}>
              Keep it
            </button>
            <button type="button" className="btn btn--danger" onClick={remove} disabled={busy}>
              {busy && <span className="spinner" />}
              Delete
            </button>
          </>
        }
      />

      <Dialog
        open={feedbackOpen}
        onClose={() => setFeedbackOpen(false)}
        title="Send it back"
        description="This re-drafts the piece with your notes. It returns to manual review and won't auto-publish again."
        footer={
          <>
            <button type="button" className="btn btn--ghost" onClick={() => setFeedbackOpen(false)} disabled={busy}>
              Cancel
            </button>
            <button type="button" className="btn btn--lav" onClick={sendFeedback} disabled={busy || !feedback.trim()}>
              {busy && <span className="spinner" />}
              Pull and re-draft
            </button>
          </>
        }
      >
        <div>
          <label className="field-label" htmlFor="topic-feedback">Notes for the writer</label>
          <textarea
            id="topic-feedback"
            className="input"
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            placeholder="Tighten the intro, lead with the ₹-figure, drop the second case study…"
          />
        </div>
      </Dialog>
    </div>
  )
}

/* ── The action stack, matched to what the pipeline can actually do ───────── */

/**
 * `published_url` is written by the publisher agent from what an LLM tool
 * call reports back, with no schema check between that call and the database
 * column (`swarm/tools/supabase_tool.py:db_upsert_blog_post` accepts an
 * arbitrary dict). If a prompt injection ever reached that step, the stored
 * value could be a `javascript:` or `data:` URI rather than a real post URL —
 * and this is the one place in the dashboard that renders it as a clickable
 * `<a href>`. Only ever hand the browser an http(s) link.
 */
function isPublicHttpUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

interface ActionStackProps {
  topic: Topic
  post: BlogPost | null
  busy: boolean
  onApprove: () => void
  onFeedback: () => void
  onReset: () => void
  onRerun: () => void
}

function ActionStack({ topic, post, busy, onApprove, onFeedback, onReset, onRerun }: ActionStackProps) {
  const status = topic.status

  if (status === 'verifying_research' || status === 'verifying_draft' || status === 'scheduled') {
    return (
      <>
        <button type="button" className="btn btn--lav" onClick={onApprove} disabled={busy}>
          {busy && <span className="spinner" />}
          {status === 'scheduled' ? 'Publish it now' : 'Approve and continue'}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onFeedback} disabled={busy}>
          Send feedback
        </button>
      </>
    )
  }

  if (status === 'failed') {
    const recoverable = Boolean(post?.mdx_final || post?.research_json)
    return (
      <>
        {recoverable && (
          <button type="button" className="btn btn--lav" onClick={onReset} disabled={busy}>
            {busy && <span className="spinner" />}
            Reset to review
          </button>
        )}
        <button type="button" className="btn btn--ghost" onClick={onRerun} disabled={busy}>
          Re-run from research
        </button>
        <p className="t-sm muted">
          {post?.mdx_final
            ? 'The draft survived the crash. Reset reviews it rather than paying to write it again.'
            : post?.research_json
              ? 'Research survived the crash. Reset continues from there.'
              : 'Nothing was saved before it crashed, so this starts over.'}
        </p>
      </>
    )
  }

  if (statusMeta(status).live) {
    return <p className="t-base muted">Running · nothing to do. The log to the left is live.</p>
  }

  if (status === 'published') {
    const url = post?.published_url
    return url && isPublicHttpUrl(url)
      ? <a className="btn btn--ghost" href={url} target="_blank" rel="noreferrer">View the live post ↗</a>
      : <p className="t-base muted">
          {url ? 'Published, but the recorded URL is not a safe link to open.' : 'Published. No live URL was recorded for this post.'}
        </p>
  }

  return (
    <button type="button" className="btn btn--lav" onClick={onRerun} disabled={busy}>
      {busy && <span className="spinner" />}
      Start research now
    </button>
  )
}

/* ── Video kit ───────────────────────────────────────────────────────────── */

function VideoPanel({ kit, slug }: { kit: VideoKit | null; slug: string }) {
  if (!kit) {
    return (
      <div aria-busy="true">
        <div className="code" style={{ height: 200 }} />
      </div>
    )
  }

  const props = JSON.stringify(kit.props, null, 2)
  const commands = [kit.commands.studio, kit.commands.vertical, kit.commands.landscape].join('\n\n')

  return (
    <>
      <div className="row wrap gap-12 mb-18" style={{ justifyContent: 'space-between' }}>
        <div>
          <h2 className="section-title" style={{ fontSize: 'var(--text-lg)' }}>Remotion video kit</h2>
          <p className="section-note">
            Vertical and landscape blog promos, rendered from the finished post.
          </p>
        </div>
        <span className="chip chip--teal">Ready</span>
      </div>

      <div className="grid-halves">
        <div>
          <div className="row gap-10" style={{ marginBottom: 9 }}>
            <span className="t-sm" style={{ color: 'var(--ink-mute)', fontWeight: 500 }}>Video props</span>
            <CopyButton text={props} label="Video props" className="btn btn--ghost btn--xs push" />
          </div>
          <pre className="code scroller" style={{ maxHeight: 340 }}>{props}</pre>
        </div>
        <div>
          <div className="row gap-10" style={{ marginBottom: 9 }}>
            <span className="t-sm" style={{ color: 'var(--ink-mute)', fontWeight: 500 }}>Commands</span>
            <CopyButton text={commands} label="Commands" className="btn btn--ghost btn--xs push" />
          </div>
          <pre className="code code--dark scroller" style={{ maxHeight: 340 }}>{commands}</pre>
        </div>
      </div>

      <p className="t-sm muted" style={{ marginTop: 14 }}>
        Renders land in <code className="mono">out/{slug}-vertical.mp4</code> and{' '}
        <code className="mono">out/{slug}-landscape.mp4</code>.
      </p>
    </>
  )
}
