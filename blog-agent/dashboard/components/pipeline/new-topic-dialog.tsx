'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import type { Topic } from '../../lib/types'
import { Dialog } from '../ui/dialog'
import { useToast } from '../ui/toast'

interface Props {
  open: boolean
  onClose: () => void
  onCreated: (topic: Topic) => void
}

/**
 * Brief the village.
 *
 * The old version polled `/api/topic/<slug>` fifteen times waiting for the row
 * to appear before navigating, holding the dialog open for up to fifteen
 * seconds on a slow start. The job is asynchronous by design, so this now adds
 * the topic optimistically, closes, and lets the board's poll reconcile — the
 * operator gets their board back immediately and the topic appears in the
 * queued lane either way.
 */
export function NewTopicDialog({ open, onClose, onCreated }: Props) {
  const router = useRouter()
  const { toast } = useToast()
  const [title, setTitle] = useState('')
  const [tags, setTags] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!title.trim() || busy) return

    setBusy(true)
    setError('')
    const tagList = tags.split(',').map(t => t.trim()).filter(Boolean)

    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim(), tags: tagList }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setError(data.error || 'Could not start the research pipeline.')
        setBusy(false)
        return
      }

      const now = new Date().toISOString()
      onCreated({
        id: `pending:${data.slug}`,
        slug: data.slug,
        title: title.trim(),
        status: 'queued',
        tags: tagList,
        created_at: now,
        updated_at: now,
        scheduled_for: null,
      })

      toast('Research started')
      setTitle('')
      setTags('')
      onClose()
      router.push(`/topic/${data.slug}`)
    } catch {
      setError('Could not reach the server.')
      setBusy(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Brief the village"
      description="It gets researched across nine sources, audited, written and humanised, then queued for your review."
    >
      <form onSubmit={submit} className="stack gap-14">
        <div>
          <label className="field-label" htmlFor="topic-title">Topic or working title</label>
          <input
            id="topic-title"
            className="input"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Vision AI for pharma blister-pack inspection"
            required
            aria-describedby={error ? 'new-topic-error' : undefined}
          />
        </div>

        <div>
          <label className="field-label" htmlFor="topic-tags">Tags</label>
          <input
            id="topic-tags"
            className="input"
            value={tags}
            onChange={e => setTags(e.target.value)}
            placeholder="computer-vision, manufacturing, india"
          />
        </div>

        {error && (
          <p id="new-topic-error" className="notice notice--rose t-base" role="alert">{error}</p>
        )}

        <div className="dialog-actions">
          <button type="button" className="btn btn--ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="btn btn--lav" disabled={busy || !title.trim()}>
            {busy && <span className="spinner" />}
            Start research
          </button>
        </div>
      </form>
    </Dialog>
  )
}
