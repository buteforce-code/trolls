'use client'

import { useEffect, useState } from 'react'
import type { Topic } from '../../lib/types'
import { Dialog } from '../ui/dialog'
import { useToast } from '../ui/toast'

interface Props {
  topic: Topic | null
  onClose: () => void
  onSubmitted: () => void
}

/**
 * Send it back.
 *
 * `POST /api/reject` requires non-empty feedback, and rightly so — a rejection
 * with no note gives the writer agent nothing to change, and the topic comes
 * back identical. The submit button stays disabled until there is something to
 * act on.
 */
export function FeedbackDialog({ topic, onClose, onSubmitted }: Props) {
  const { toast } = useToast()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { setText(''); setError('') }, [topic?.slug])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!topic || !text.trim() || busy) return

    setBusy(true)
    setError('')
    try {
      const res = await fetch('/api/reject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug: topic.slug, feedback: text.trim() }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setError(data.error || 'Could not send the feedback.')
        setBusy(false)
        return
      }
      toast('Pulled off the schedule, re-drafting')
      onSubmitted()
      onClose()
    } catch {
      setError('Could not reach the server.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open={topic !== null}
      onClose={onClose}
      title="Send it back"
      description={
        topic
          ? `This pulls “${topic.title}” off the schedule and re-drafts it with your notes. It returns to manual review and won't auto-publish again.`
          : ''
      }
    >
      <form onSubmit={submit} className="stack gap-14">
        <div>
          <label className="field-label" htmlFor="feedback-text">Notes for the writer</label>
          <textarea
            id="feedback-text"
            className="input"
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Tighten the intro, lead with the ₹-figure, drop the second case study…"
            required
            aria-describedby={error ? 'feedback-error' : undefined}
          />
        </div>

        {error && (
          <p id="feedback-error" className="notice notice--rose t-base" role="alert">{error}</p>
        )}

        <div className="dialog-actions">
          <button type="button" className="btn btn--ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="btn btn--lav" disabled={busy || !text.trim()}>
            {busy && <span className="spinner" />}
            Pull and re-draft
          </button>
        </div>
      </form>
    </Dialog>
  )
}
