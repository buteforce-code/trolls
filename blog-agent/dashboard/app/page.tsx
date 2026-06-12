'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'

// ── Types ────────────────────────────────────────────────────────────────────
type Topic = {
  id: string
  slug: string
  title: string
  status: string
  tags: string[]
  updated_at: string
  scheduled_for?: string | null
}

type AutopilotState = {
  enabled: boolean
  gapHours: number
  scheduled: { slug: string; title: string; scheduled_for: string }[]
  nextPublishAt?: string | null
}

// ── Status display helpers ────────────────────────────────────────────────────
const STATUS_LABEL: Record<string, string> = {
  queued:             'Queued',
  researching:        'Researching',
  verifying_research: 'Review Research',
  writing:            'Writing',
  verifying_draft:    'Review Draft',
  scheduled:          'Scheduled',
  publishing:         'Publishing',
  published:          'Published',
  cancelled:          'Cancelled',
  failed:             'Failed',
}

// Future-friendly relative time ("in 3h", "in 2d") for scheduled slots.
function until(dt: string): string {
  const diff = new Date(dt).getTime() - Date.now()
  if (diff <= 0) return 'now'
  const m = Math.round(diff / 60000)
  if (m < 60) return `in ${m}m`
  const h = Math.round(m / 60)
  if (h < 48) return `in ${h}h`
  return `in ${Math.round(h / 24)}d`
}

function relative(dt: string): string {
  const diff = Date.now() - new Date(dt).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1)  return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

// ── TopicCard ─────────────────────────────────────────────────────────────────
function TopicCard({ topic, onDelete }: { topic: Topic; onDelete: (slug: string) => void }) {
  const [deleting, setDeleting]       = useState(false)
  const [confirmDelete, setConfirm]   = useState(false)

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!confirmDelete) { setConfirm(true); return }
    setDeleting(true)
    try {
      await fetch('/api/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug: topic.slug }),
      })
      // Remove from UI immediately — Python will clean up DB in background
      onDelete(topic.slug)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="card card-link" style={{ position: 'relative' }}>
      {/* Delete control — top right corner */}
      <div
        style={{ position: 'absolute', top: 12, right: 12, zIndex: 2 }}
        onClick={e => { e.preventDefault(); e.stopPropagation() }}
      >
        {confirmDelete ? (
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Delete?</span>
            <button
              className="btn btn-sm btn-danger"
              style={{ padding: '3px 8px', fontSize: 11 }}
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? '...' : 'Yes'}
            </button>
            <button
              className="btn btn-sm btn-outline"
              style={{ padding: '3px 8px', fontSize: 11 }}
              onClick={e => { e.preventDefault(); e.stopPropagation(); setConfirm(false) }}
            >
              No
            </button>
          </div>
        ) : (
          <button
            onClick={handleDelete}
            className="card-delete-btn"
            title="Delete topic"
          >
            ×
          </button>
        )}
      </div>

      <Link href={`/topic/${topic.slug}`} style={{ display: 'block' }}>
        <div className="topic-card-header" style={{ paddingRight: 60 }}>
          <div className="topic-card-title">{topic.title}</div>
          <span className={`badge badge-${topic.status}`}>
            {STATUS_LABEL[topic.status] ?? topic.status}
          </span>
        </div>
        <div className="topic-card-slug">/{topic.slug}</div>
        <div className="topic-card-tags">
          {(topic.tags || []).map(t => (
            <span key={t} className="tag">{t}</span>
          ))}
        </div>
        <div className="topic-card-meta">
          {topic.status === 'scheduled' && topic.scheduled_for
            ? <span style={{ color: '#7c3aed', fontWeight: 600 }}>Auto-publishes {until(topic.scheduled_for)}</span>
            : relative(topic.updated_at)}
        </div>
      </Link>
    </div>
  )
}

// ── New Topic Modal ───────────────────────────────────────────────────────────
function NewTopicModal({ onClose, onCreated }: { onClose: () => void; onCreated: (topic: Topic) => void }) {
  const router = useRouter()
  const [title, setTitle]     = useState('')
  const [tags, setTags]       = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const [statusText, setStatusText] = useState('')

  async function submit(e: { preventDefault(): void }) {
    e.preventDefault()
    if (!title.trim()) return
    setLoading(true)
    setError('')
    setStatusText('Starting the research pipeline on the server...')
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim(), tags: tags.split(',').map(t => t.trim()).filter(Boolean) }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed to start')
      const slug = data.slug as string
      const optimisticTopic: Topic = {
        id: `pending:${slug}`,
        slug,
        title: title.trim(),
        status: 'queued',
        tags: tags.split(',').map(t => t.trim()).filter(Boolean),
        updated_at: new Date().toISOString(),
      }
      onCreated(optimisticTopic)
      setStatusText(`Job queued as /${slug}. Waiting for the topic record...`)

      for (let attempt = 0; attempt < 15; attempt += 1) {
        await new Promise(r => setTimeout(r, 1000))
        const topicRes = await fetch(`/api/topic/${slug}`)
        if (topicRes.ok) {
          router.push(`/topic/${slug}`)
          onClose()
          return
        }
      }

      setStatusText(`Job started as /${slug}. The dashboard will refresh automatically if it takes longer to appear.`)
      onClose()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h2>New Blog Topic</h2>
        <p>The agent will research it across 9 sources, write, humanise, and queue it for your review.</p>
        <form onSubmit={submit}>
          <div className="field">
            <label>Topic / Working Title *</label>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="e.g. AI agents are replacing junior developers"
              autoFocus
              required
            />
          </div>
          <div className="field">
            <label>Tags</label>
            <input
              value={tags}
              onChange={e => setTags(e.target.value)}
              placeholder="ai, agents, engineering (comma separated)"
            />
            <div className="field-hint">Used for filtering and blog taxonomy.</div>
          </div>
          {statusText && <div style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 12 }}>{statusText}</div>}
          {error && <div style={{ color: 'var(--red)', fontSize: 13, marginBottom: 12 }}>{error}</div>}
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 12 }}>
            Raw execution logs appear in the server logs, not in the browser console.
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-outline" onClick={onClose} disabled={loading}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading || !title.trim()}>
              {loading ? <><span className="spinner" /> Starting research...</> : '→ Start Research'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Autopilot status strip ────────────────────────────────────────────────────
function AutopilotBar({ state }: { state: AutopilotState | null }) {
  if (!state) return null
  const next = state.scheduled[0]
  return (
    <div
      className="card"
      style={{
        display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
        marginBottom: 20, padding: '12px 16px',
        borderColor: state.enabled ? 'rgba(124,58,237,0.25)' : 'var(--border)',
        background: state.enabled ? 'rgba(124,58,237,0.04)' : 'transparent',
      }}
    >
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: 13 }}>
        <span
          aria-hidden
          style={{
            width: 9, height: 9, borderRadius: '50%',
            background: state.enabled ? '#7c3aed' : '#9ca3af',
            animation: state.enabled ? 'pulse 1.4s ease-in-out infinite' : 'none',
          }}
        />
        Autopilot {state.enabled ? 'On' : 'Paused'}
      </span>
      <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
        1 post every {state.gapHours}h
      </span>
      {state.scheduled.length > 0 ? (
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          · {state.scheduled.length} scheduled
          {next && <> · next <strong style={{ color: '#7c3aed' }}>{until(next.scheduled_for)}</strong></>}
        </span>
      ) : (
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>· nothing scheduled yet</span>
      )}
      <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-muted)' }}>
        Scheduled posts auto-publish unless you reject them first.
      </span>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [topics, setTopics]       = useState<Topic[]>([])
  const [loading, setLoading]     = useState(true)
  const [activeTag, setActiveTag] = useState<string | null>(null)
  const [modal, setModal]         = useState(false)
  const [autopilot, setAutopilot] = useState<AutopilotState | null>(null)

  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())

  const load = useCallback(async (): Promise<Topic[]> => {
    try {
      const res = await fetch('/api/topics')
      const data = await res.json()
      const next: Topic[] = data.topics || []
      setTopics(next)
      setLastRefresh(new Date())
      // Refresh autopilot status alongside topics (best-effort, non-blocking).
      fetch('/api/autopilot')
        .then(r => (r.ok ? r.json() : null))
        .then(s => { if (s) setAutopilot(s) })
        .catch(() => {})
      return next
    } catch {
      return []
    } finally {
      setLoading(false)
    }
  }, [])

  // Adaptive polling: 3s when any topic is actively processing, 10s otherwise.
  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const ACTIVE = new Set(['queued', 'researching', 'writing', 'publishing'])

    const loop = async (): Promise<void> => {
      if (cancelled) return
      const fresh = await load()
      if (cancelled) return
      const delay = fresh.some(t => ACTIVE.has(t.status)) ? 3000 : 10000
      timer = setTimeout(loop, delay)
    }
    loop()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [load])

  const handleDelete = (slug: string) => {
    setTopics(prev => prev.filter(t => t.slug !== slug))
  }

  const handleCreated = (topic: Topic) => {
    setTopics(prev => [topic, ...prev.filter(existing => existing.slug !== topic.slug)])
  }

  const allTags  = Array.from(new Set(topics.flatMap(t => t.tags || [])))
  const filtered = activeTag ? topics.filter(t => (t.tags || []).includes(activeTag)) : topics

  const counts = {
    total:     topics.length,
    pending:   topics.filter(t => ['verifying_research', 'verifying_draft'].includes(t.status)).length,
    published: topics.filter(t => t.status === 'published').length,
    failed:    topics.filter(t => t.status === 'failed').length,
  }

  return (
    <main>
      <div className="container">
        <div className="page-header">
          <div className="page-header-row">
            <div>
              <h1>Blog Topics</h1>
              <p>
                {counts.total} topics
                {counts.pending > 0  && <> · <span style={{ color: 'var(--amber)' }}>{counts.pending} need review</span></>}
                {counts.published > 0 && <> · {counts.published} published</>}
                {counts.failed > 0    && <> · <span style={{ color: 'var(--red)' }}>{counts.failed} failed</span></>}
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span
                title={`Last refresh: ${lastRefresh.toLocaleTimeString()}`}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-muted)' }}
              >
                <span
                  aria-hidden
                  style={{
                    width: 8, height: 8, borderRadius: '50%',
                    background: 'var(--green, #16a34a)',
                    animation: 'pulse 1.2s ease-in-out infinite',
                  }}
                />
                Live
              </span>
              <button className="btn btn-primary" onClick={() => setModal(true)}>
                + New Topic
              </button>
            </div>
          </div>
        </div>

        {/* Autopilot status */}
        <AutopilotBar state={autopilot} />

        {/* Tag filter */}
        {allTags.length > 0 && (
          <div className="filters">
            <span className="filter-label">Filter:</span>
            <button className={`tag ${!activeTag ? 'active' : ''}`} onClick={() => setActiveTag(null)}>
              All
            </button>
            {allTags.map(tag => (
              <button
                key={tag}
                className={`tag ${activeTag === tag ? 'active' : ''}`}
                onClick={() => setActiveTag(activeTag === tag ? null : tag)}
              >
                {tag}
              </button>
            ))}
          </div>
        )}

        {/* Grid */}
        {loading ? (
          <div className="empty">
            <div className="empty-icon">⏳</div>
            <h2>Loading topics...</h2>
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty">
            <div className="empty-icon">✦</div>
            <h2>{activeTag ? `No topics tagged "${activeTag}"` : 'No topics yet'}</h2>
            <p>Click <strong>+ New Topic</strong> to start the research pipeline.</p>
          </div>
        ) : (
          <div className="topic-grid">
            {filtered.map(t => <TopicCard key={t.id} topic={t} onDelete={handleDelete} />)}
          </div>
        )}
      </div>

      {modal && (
        <NewTopicModal
          onClose={() => setModal(false)}
          onCreated={handleCreated}
        />
      )}
    </main>
  )
}
