'use client'

import { useState, useEffect, useCallback, useRef, use } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'

// ── Components ───────────────────────────────────────────────────────────────
function PipelineStep({ label, status, expected }: { label: string, status: string, expected: string[] }) {
  const [isActive, isDone] = (() => {
    if (expected.includes(status)) return [true, false]
    const order = ['queued', 'researching', 'verifying_research', 'writing', 'verifying_draft', 'publishing', 'published', 'failed']
    const currentIndex = order.indexOf(status)
    const expectedIndices = expected.map(e => order.indexOf(e))
    const expectedMax = Math.max(...expectedIndices)
    if (currentIndex > expectedMax) return [false, true]
    return [false, false]
  })()

  const cls = `pipeline-step ${isActive ? 'active' : ''} ${isDone ? 'done' : ''}`
  return (
    <div className={cls}>
      <div className="pipeline-step-dot" />
      <span>{label}</span>
    </div>
  )
}

export default function TopicPage({ params }: { params: Promise<{ slug: string }> }) {
  const router = useRouter()
  const { slug } = use(params)

  const [topic, setTopic]               = useState<any>(null)
  const [post, setPost]                 = useState<any>(null)
  const [loading, setLoading]           = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [showReject, setShowReject]     = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [feedback, setFeedback]         = useState('')
  const [logLines, setLogLines]         = useState<string[]>([])
  const [videoKit, setVideoKit]         = useState<any>(null)
  const logCursorRef = useRef(0)
  const mountedRef = useRef(true)

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/topic/${slug}`)
      if (!res.ok) {
        if (res.status === 404) router.replace('/')
        return
      }
      const data = await res.json()
      setTopic(data.topic)
      setPost(data.post)
    } finally {
      setLoading(false)
    }
  }, [slug, router])

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    load()
    const iv = setInterval(() => {
      setTopic((t: any) => {
        if (!t) return t
        const active = ['queued', 'researching', 'writing', 'publishing'].includes(t.status)
        if (active) load()
        return t
      })
    }, 4000)
    return () => clearInterval(iv)
  }, [load])

  // Poll job logs (always on — file may exist for completed/failed jobs too)
  useEffect(() => {
    let cancelled = false
    const fetchLogs = async () => {
      try {
        const res = await fetch(`/api/topic/${slug}/logs?after=${logCursorRef.current}`)
        if (!res.ok || cancelled) return
        const data = await res.json()
        if (cancelled) return
        if (Array.isArray(data.lines) && data.lines.length > 0) {
          setLogLines(prev => [...prev, ...data.lines].slice(-500))
        }
        if (typeof data.totalBytes === 'number') logCursorRef.current = data.totalBytes
      } catch {}
    }
    fetchLogs()
    const iv = setInterval(fetchLogs, 3000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [slug])

  if (loading || !topic) {
    return <div className="empty">Loading...</div>
  }

  const needsReview = ['verifying_research', 'verifying_draft'].includes(topic.status)
  const isFailed    = topic.status === 'failed'
  const isPublished = topic.status === 'published'
  const isRunning   = ['queued', 'researching', 'writing', 'publishing'].includes(topic.status)

  // Stuck detection — running but updated_at hasn't moved in >5 min
  const STUCK_THRESHOLD_MS = 5 * 60 * 1000
  const updatedMs = topic.updated_at ? new Date(topic.updated_at).getTime() : 0
  const ageMs = updatedMs ? Date.now() - updatedMs : 0
  const isStuck = isRunning && ageMs > STUCK_THRESHOLD_MS

  const statusHelp: Record<string, string> = {
    queued: 'The job has been accepted and should begin shortly.',
    researching: 'The agent is gathering site context and external sources.',
    writing: 'The writer, humaniser, image pipeline, and linker are running.',
    publishing: 'The approved post is being pushed live.',
  }

  let digest = null
  try { digest = post?.research_json ? JSON.parse(post.research_json) : null } catch {}

  // ── Actions ──────────────────────────────────────────────────────────────
  const handleApprove = async () => {
    setActionLoading(true)
    try {
      await fetch('/api/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug }),
      })
      setTopic({ ...topic, status: topic.status === 'verifying_research' ? 'writing' : 'publishing' })
      setShowReject(false)
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (!feedback.trim()) return
    setActionLoading(true)
    try {
      await fetch('/api/reject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug, feedback }),
      })
      setTopic({ ...topic, status: topic.status === 'verifying_research' ? 'researching' : 'writing' })
      setFeedback('')
      setShowReject(false)
    } finally {
      setActionLoading(false)
    }
  }

  const handleDelete = async () => {
    setActionLoading(true)
    try {
      await fetch('/api/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug }),
      })
      // Python runs detached — give it 1.5s then redirect home
      await new Promise(r => setTimeout(r, 1500))
      router.replace('/')
    } finally {
      setActionLoading(false)
      setShowDeleteConfirm(false)
    }
  }

  const handleReset = async () => {
    setActionLoading(true)
    try {
      await fetch('/api/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug }),
      })
      // Python runs detached — poll until status changes away from "failed"
      for (let i = 0; i < 8; i++) {
        await new Promise(r => setTimeout(r, 800))
        const res = await fetch(`/api/topic/${slug}`)
        if (res.ok) {
          const data = await res.json()
          if (data.topic?.status !== 'failed') {
            if (mountedRef.current) {
              setTopic(data.topic)
              setPost(data.post)
            }
            return
          }
        }
      }
      // Fallback: reload anyway
      await load()
    } finally {
      setActionLoading(false)
    }
  }

  const handleRetryResearch = async () => {
    setActionLoading(true)
    try {
      await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: topic.title, tags: topic.tags }),
      })
      setTopic({ ...topic, status: 'researching' })
    } finally {
      setActionLoading(false)
    }
  }

  const handleVideoKit = async () => {
    setActionLoading(true)
    try {
      const res = await fetch(`/api/topic/${slug}/video`)
      if (res.ok) setVideoKit(await res.json())
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <main className="container">
      <div style={{ marginTop: 24, marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Link href="/" className="text-muted text-sm">← Back to Dashboard</Link>
        {/* Delete button — always visible */}
        {!showDeleteConfirm ? (
          <button
            className="btn btn-sm"
            style={{ color: 'var(--red)', border: '1px solid rgba(220,38,38,0.25)', background: 'rgba(220,38,38,0.05)', fontSize: 12 }}
            onClick={() => setShowDeleteConfirm(true)}
            disabled={actionLoading}
          >
            Delete Topic
          </button>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Are you sure?</span>
            <button className="btn btn-sm btn-danger" onClick={handleDelete} disabled={actionLoading}>
              {actionLoading ? 'Deleting...' : 'Yes, delete'}
            </button>
            <button className="btn btn-sm btn-outline" onClick={() => setShowDeleteConfirm(false)} disabled={actionLoading}>
              Cancel
            </button>
          </div>
        )}
      </div>

      <div className="topic-detail">
        {/* Left: Pipeline Sidebar */}
        <div className="pipeline-sidebar">
          <div className="pipeline-title">Pipeline Status</div>
          <div className="pipeline-steps">
            <PipelineStep label="1. Researching"          status={topic.status} expected={['queued', 'researching']} />
            <PipelineStep label="2. Verify Research"      status={topic.status} expected={['verifying_research']} />
            <PipelineStep label="3. Writing & Humanising" status={topic.status} expected={['writing']} />
            <PipelineStep label="4. Verify Draft"         status={topic.status} expected={['verifying_draft']} />
            <PipelineStep label="5. Publishing"           status={topic.status} expected={['publishing']} />
            <PipelineStep label="6. Done"                 status={topic.status} expected={['published']} />
          </div>

          {/* Failed state — recovery options */}
          {isFailed && (
            <div style={{ marginTop: 20 }}>
              <div style={{
                padding: '12px 14px',
                background: 'rgba(220,38,38,0.06)',
                border: '1px solid rgba(220,38,38,0.2)',
                borderRadius: 'var(--radius-sm)',
                marginBottom: 12,
              }}>
                <div style={{ fontWeight: 700, color: 'var(--red)', fontSize: 13, marginBottom: 4 }}>Pipeline failed</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                  {post?.mdx_final
                    ? 'The draft is ready. Reset to review it and publish.'
                    : post?.research_json
                    ? 'Research is ready. Reset to review and continue writing.'
                    : 'No content saved. Retry research from scratch.'}
                </div>
              </div>

              {/* Smart reset — goes to the right review stage */}
              {(post?.mdx_final || post?.research_json) && (
                <button
                  className="btn btn-success"
                  style={{ width: '100%', justifyContent: 'center', marginBottom: 8 }}
                  onClick={handleReset}
                  disabled={actionLoading}
                >
                  {actionLoading ? <><span className="spinner" /> Working...</> : '↩ Reset to Review'}
                </button>
              )}

              {/* Retry from scratch */}
              <button
                className="btn btn-outline"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={handleRetryResearch}
                disabled={actionLoading}
              >
                {actionLoading ? <><span className="spinner" /> Starting...</> : '↺ Re-run Research'}
              </button>
            </div>
          )}

          {/* Published — live link */}
          {isPublished && post?.published_url && (
            <div style={{ marginTop: 24 }}>
              <a href={post.published_url} target="_blank" rel="noreferrer"
                className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}>
                View Live Post ↗
              </a>
            </div>
          )}

          {(post?.mdx_final || digest) && (
            <div style={{ marginTop: 12 }}>
              <button
                className="btn btn-outline"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={handleVideoKit}
                disabled={actionLoading}
              >
                {actionLoading ? <><span className="spinner" /> Preparing...</> : 'Generate Remotion Kit'}
              </button>
            </div>
          )}
        </div>

        {/* Right: Content Area */}
        <div className="topic-content">
          <h1 className="topic-content-title">{topic.title}</h1>
          <div className="topic-content-meta">
            <span className="badge badge-queued">{topic.slug}</span>
            {(topic.tags || []).map((t: string) => <span key={t} className="tag">{t}</span>)}
          </div>

          {videoKit && (
            <div className="card remotion-kit">
              <div className="remotion-kit-header">
                <div>
                  <div className="remotion-kit-label">Remotion Video Kit</div>
                  <div className="remotion-kit-title">Blog promo and landscape social render</div>
                </div>
                <span className="tag active">Ready</span>
              </div>
              <div className="remotion-kit-grid">
                <div>
                  <div className="digest-section-label">Video Props</div>
                  <pre className="remotion-code">{JSON.stringify(videoKit.props, null, 2)}</pre>
                </div>
                <div>
                  <div className="digest-section-label">Commands</div>
                  <pre className="remotion-code">{`${videoKit.commands.studio}\n\n${videoKit.commands.vertical}\n\n${videoKit.commands.landscape}`}</pre>
                </div>
              </div>
            </div>
          )}

          {isRunning && !isStuck && (
            <div className="card" style={{ marginBottom: 20, borderColor: 'rgba(245,158,11,0.22)', background: 'rgba(245,158,11,0.05)' }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Pipeline running in background</div>
              <div style={{ color: 'var(--text-muted)', fontSize: 14, lineHeight: 1.6 }}>
                {statusHelp[topic.status] || 'The agent is working.'} This page refreshes automatically every few seconds.
                Live job output is shown below.
              </div>
            </div>
          )}

          {isStuck && (
            <div className="card" style={{ marginBottom: 20, borderColor: 'rgba(220,38,38,0.25)', background: 'rgba(220,38,38,0.06)' }}>
              <div style={{ fontWeight: 700, marginBottom: 6, color: 'var(--red)' }}>
                Pipeline appears stuck
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: 14, lineHeight: 1.6, marginBottom: 12 }}>
                Status is <code>{topic.status}</code> but no progress in {Math.floor(ageMs / 60000)} min.
                The Python worker likely crashed before updating the database. Check the logs below, then retry or delete.
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <button className="btn btn-primary btn-sm" onClick={handleRetryResearch} disabled={actionLoading}>
                  {actionLoading ? <><span className="spinner" /> Starting...</> : '↺ Re-run from scratch'}
                </button>
                <button
                  className="btn btn-sm btn-outline"
                  style={{ color: 'var(--red)', borderColor: 'rgba(220,38,38,0.3)' }}
                  onClick={() => setShowDeleteConfirm(true)}
                  disabled={actionLoading}
                >
                  Delete topic
                </button>
              </div>
            </div>
          )}

          {/* Live job logs */}
          {(isRunning || isFailed || logLines.length > 0) && (
            <div className="card" style={{ marginBottom: 20, padding: 0, overflow: 'hidden' }}>
              <div style={{
                padding: '10px 14px',
                borderBottom: '1px solid var(--border)',
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: 0.5,
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}>
                <span>Job Logs {isRunning && <span style={{ color: 'var(--green, #16a34a)', fontWeight: 600 }}>● live</span>}</span>
                <span style={{ fontWeight: 400 }}>{logLines.length} line{logLines.length === 1 ? '' : 's'}</span>
              </div>
              <pre style={{
                margin: 0,
                padding: '12px 14px',
                background: '#0a0a0a',
                color: '#d4d4d8',
                fontSize: 12,
                lineHeight: 1.5,
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                maxHeight: 320,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}>
                {logLines.length === 0
                  ? '(no log output yet — file may not exist or job has not produced output)'
                  : logLines.join('\n')}
              </pre>
            </div>
          )}

          {/* Research Digest */}
          {digest && (topic.status === 'verifying_research' || topic.status === 'writing' || (isFailed && !post?.mdx_final)) && (
            <div className="card digest-card">
              <div className="digest-card-title">Research Digest</div>

              {(digest._parse_error || !digest.summary) && (
                <div
                  style={{
                    background: 'rgba(220,38,38,0.08)',
                    border: '1px solid rgba(220,38,38,0.25)',
                    color: 'var(--red, #dc2626)',
                    padding: '12px 14px',
                    borderRadius: 8,
                    fontSize: 13,
                    marginBottom: 16,
                  }}
                >
                  <strong>Digest is incomplete.</strong>{' '}
                  {digest._parse_error
                    ? `Reason: ${digest._parse_error}.`
                    : 'The research agent returned no usable content.'}
                  {' '}Click <em>Re-run Research</em> on the right to retry.
                  {digest.raw && (
                    <details style={{ marginTop: 8 }}>
                      <summary style={{ cursor: 'pointer', color: 'var(--text-muted)' }}>Show raw agent output</summary>
                      <pre style={{ whiteSpace: 'pre-wrap', fontSize: 11, marginTop: 6, maxHeight: 240, overflow: 'auto' }}>
                        {digest.raw}
                      </pre>
                    </details>
                  )}
                </div>
              )}

              <div className="digest-section">
                <div className="digest-section-label">Summary</div>
                <div className="digest-section-value">{digest.summary || digest.topic}</div>
              </div>

              <div className="digest-section">
                <div className="digest-section-label">The Discourse</div>
                <div className="digest-section-value">{digest.what_people_say}</div>
              </div>

              <div className="digest-section">
                <div className="digest-section-label">Buteforce Angle</div>
                <div className="digest-section-value" style={{ color: '#0a0a0a', fontWeight: 600 }}>{digest.buteforce_angle}</div>
              </div>

              <div className="digest-section">
                <div className="digest-section-label">Key Facts</div>
                <div className="digest-facts">
                  {(digest.key_facts || []).map((f: string, i: number) => <div key={i} className="digest-fact">{f}</div>)}
                </div>
              </div>

              <div className="digest-section">
                <div className="digest-section-label">Source Signals</div>
                <div className="source-grid">
                  {Object.entries(digest.source_signals || {}).map(([key, val]) =>
                    val ? (
                      <div key={key} className="source-item">
                        <div className="source-name">{key}</div>
                        <div className="source-text">{val as string}</div>
                      </div>
                    ) : null
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Final draft */}
          {post?.mdx_final && (
            <div className="blog-preview">
              <div className="blog-preview-bar">
                <div className="blog-preview-label">Final Blog Post (.mdx)</div>
                <div className="blog-preview-stats">
                  <div className="blog-preview-stat">{post.word_count || 0} words</div>
                </div>
              </div>
              <div className="blog-preview-content">{post.mdx_final}</div>
            </div>
          )}

          {/* Rough draft (writing in progress) */}
          {post?.mdx_draft && !post?.mdx_final && topic.status === 'writing' && (
            <div className="blog-preview" style={{ marginTop: 24, opacity: 0.5 }}>
              <div className="blog-preview-bar">
                <div className="blog-preview-label">Initial Draft (Pre-Humaniser)</div>
              </div>
              <div className="blog-preview-content" style={{ maxHeight: 200 }}>{post.mdx_draft}</div>
            </div>
          )}

          {/* APPROVAL ACTIONS */}
          {needsReview && (
            <div className="pipeline-actions">
              <div className="pipeline-actions-title">
                {topic.status === 'verifying_research'
                  ? 'Do you approve this research angle?'
                  : 'Do you approve this draft for publishing?'}
              </div>
              <div className="pipeline-actions-row">
                <button className="btn btn-primary" onClick={handleApprove} disabled={actionLoading}>
                  {actionLoading ? <><span className="spinner" /> Processing...</> : '✓ Approve & Continue'}
                </button>
                <button className="btn btn-outline" onClick={() => setShowReject(!showReject)} disabled={actionLoading}>
                  ✕ Send Feedback
                </button>
              </div>

              {showReject && (
                <div className="reject-panel">
                  <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)' }}>
                    What needs to change?
                  </label>
                  <textarea
                    value={feedback}
                    onChange={e => setFeedback(e.target.value)}
                    placeholder="e.g. Needs more edge, remove the mention of X, frame it around founder led sales..."
                    autoFocus
                  />
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                    <button className="btn btn-outline btn-sm" onClick={() => setShowReject(false)}>Cancel</button>
                    <button className="btn btn-danger btn-sm" onClick={handleReject} disabled={!feedback.trim() || actionLoading}>
                      {actionLoading ? 'Updating...' : 'Reject & Re-run'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
