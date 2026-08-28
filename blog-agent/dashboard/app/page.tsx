'use client'

import { Suspense, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { usePipeline } from '../lib/pipeline-context'
import { LANES, LANE_TITLE, statusMeta } from '../lib/status'
import type { Topic } from '../lib/types'
import { PageHeader, EmptyState } from '../components/ui/page-header'
import { StatCard } from '../components/ui/stat-card'
import { CadenceChart, CadenceLegend, type CadenceDay } from '../components/ui/cadence-chart'
import { useToast } from '../components/ui/toast'
import {
  CheckCircleIcon, PipelineIcon, PlusIcon, ProgressIcon, ReviewIcon,
} from '../components/ui/icons'
import { AutopilotStrip } from '../components/pipeline/autopilot-strip'
import { GoingOutNext } from '../components/pipeline/going-out-next'
import { Village } from '../components/pipeline/village'
import { TopicCard } from '../components/pipeline/topic-card'
import { LaneBar } from '../components/pipeline/lane-bar'
import { NewTopicDialog } from '../components/pipeline/new-topic-dialog'
import { FeedbackDialog } from '../components/pipeline/feedback-dialog'
import type { StatusGroup } from '../lib/status'

/** What each lane is for, in the operator's terms rather than the schema's. */
const LANE_SUBTITLE: Record<string, string> = {
  attention: 'Held at a gate or failed outright. Nothing here moves until you call it.',
  scheduled: 'Finished and waiting on the clock. These publish themselves unless you step in.',
  progress:  'Agents are working on these right now.',
  queued:    'Waiting their turn. This is the normal resting state, not a backlog.',
  published: 'Live on the blog.',
}

export default function BoardPage() {
  // `useSearchParams` makes this subtree client-rendered, so it needs its own
  // boundary or the production prerender of `/` fails.
  return (
    <Suspense fallback={<BoardSkeleton />}>
      <Board />
    </Suspense>
  )
}

function BoardSkeleton() {
  return (
    <div aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading the pipeline</span>
      <div className="card" style={{ height: 96, marginBottom: 20 }} />
      <div className="grid-stats" style={{ marginBottom: 22 }}>
        {[0, 1, 2, 3].map(i => <div key={i} className="card card--tight" style={{ height: 148 }} />)}
      </div>
      <div className="card" style={{ height: 300 }} />
    </div>
  )
}

function Board() {
  const params = useSearchParams()
  const { toast } = useToast()
  const { topics, autopilot, counts, loading, error, refresh, upsertTopic } = usePipeline()

  const [newTopicOpen, setNewTopicOpen] = useState(false)
  const [feedbackFor, setFeedbackFor] = useState<Topic | null>(null)
  const [cadence, setCadence] = useState<CadenceDay[] | null>(null)

  const lane = params.get('lane') ?? 'all'
  const query = (params.get('q') ?? '').trim().toLowerCase()

  /**
   * The overview furniture — autopilot, stat cards, cadence, the village — is
   * identical whichever lane you pick, so on a lane it is pure noise between
   * the operator and the cards they clicked through to see. It belongs to the
   * unfiltered board only.
   *
   * A search is a lane of its own for this purpose: you searched for a topic,
   * not for the engine's vital signs.
   */
  const isOverview = lane === 'all' && !query

  // Cadence is the one number on this page that does not come from the topic
  // list — it counts real `published_at` timestamps, so a topic re-published or
  // back-dated shows up on the right day rather than on the day its row moved.
  // Only the overview draws it, so only the overview pays for the request.
  useEffect(() => {
    if (!isOverview) return
    let cancelled = false
    fetch('/api/stats', { headers: { accept: 'application/json' } })
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (cancelled || !data?.cadence?.publishedByDay) return
        setCadence(data.cadence.publishedByDay as CadenceDay[])
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [isOverview])

  const matches = useMemo(() => {
    if (!query) return topics
    return topics.filter(t =>
      t.title.toLowerCase().includes(query)
      || t.slug.includes(query)
      || (t.tags ?? []).some(tag => tag.toLowerCase().includes(query)),
    )
  }, [topics, query])

  const groups = useMemo(() => (
    LANES
      .filter(l => lane === 'all' || lane === l.key)
      .map(l => ({ ...l, items: matches.filter(t => statusMeta(t.status).group === l.key) }))
      .filter(l => l.items.length > 0)
  ), [matches, lane])

  const nextOut = useMemo(() => {
    const scheduled = topics
      .filter(t => t.status === 'scheduled' && t.scheduled_for)
      .sort((a, b) => String(a.scheduled_for).localeCompare(String(b.scheduled_for)))
    return scheduled[0] ?? null
  }, [topics])

  const queuedCount = topics.filter(t => t.status === 'queued').length

  async function publishNow(topic: Topic) {
    // `--approve` is the pipeline's own "move this forward" verb; on a scheduled
    // topic that means publish. Going through Python rather than writing the row
    // here keeps every state transition in one place.
    const res = await fetch('/api/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: topic.slug }),
    })
    if (!res.ok) {
      toast('Could not publish — check the server logs', 'error')
      return
    }
    toast('Publishing now')
    refresh()
  }

  if (loading && topics.length === 0) return <BoardSkeleton />

  return (
    <div className="view-enter">
      <PageHeader
        title={query ? 'Search results' : LANE_TITLE[lane] ?? 'Pipeline'}
        subtitle={query
          ? `Matching “${params.get('q')}”`
          : isOverview
            ? 'Plan, veto and ship what the village produces.'
            : LANE_SUBTITLE[lane]}
        /* The bell now lives in PageHeader itself, so it is present on every
           view rather than only on the board. */
        actions={
          <button type="button" className="btn btn--primary" onClick={() => setNewTopicOpen(true)}>
            <PlusIcon />
            New topic
          </button>
        }
      />

      {error && (
        <p className="notice notice--rose mb-22" role="alert">
          Could not load the pipeline: {error}
        </p>
      )}

      {isOverview ? (
        /* `.overview` is a plain block on desktop and a flex column below 760px,
           where it re-orders its children so the veto card is the first thing on
           the page. See the `.ov-pair` note in components.css. */
        <div className="overview">
          <AutopilotStrip state={autopilot} queuedCount={queuedCount} onRan={refresh} />

          <div className="grid-stats mb-22">
            <StatCard
              label="Topics in play" value={topics.length} delta="live"
              sub="Across the whole village" icon={<PipelineIcon />} href="/" index={2}
            />
            <StatCard
              label="Published" value={counts.published} tone="teal"
              sub="Live on the blog" icon={<CheckCircleIcon />} href="/?lane=published" index={3}
            />
            <StatCard
              label="In progress" value={counts.progress} tone="lav" delta="running"
              sub="Agents working right now" icon={<ProgressIcon />} href="/?lane=progress" index={4}
            />
            <StatCard
              label="Needs review" value={counts.attention} tone="rose" delta="waiting on you"
              sub="Nothing moves until you call it" icon={<ReviewIcon />} href="/?lane=attention" index={5}
            />
          </div>

          {cadence && cadence.length > 0 && (
            <section className="card rise mb-22" style={{ '--i': 4 } as React.CSSProperties}>
              <div className="row wrap gap-18" style={{ justifyContent: 'space-between', marginBottom: 20 }}>
                <div>
                  <h2 className="section-title">Publishing cadence</h2>
                  <p className="section-note">
                    {cadence.reduce((a, d) => a + d.count, 0)} posts in the last {cadence.length} days
                  </p>
                </div>
                <CadenceLegend />
              </div>
              <CadenceChart days={cadence} />
            </section>
          )}

          {/* The village is ten rows tall and the veto card is three buttons
              tall, so `flex-start` left a third of this row empty. Stretch is
              explicit rather than omitted: `.row` centres by default, which
              would only split the same gap in two. */}
          <div className="row wrap gap-22 mb-22 ov-pair" style={{ alignItems: 'stretch' }}>
            <GoingOutNext
              topic={nextOut}
              onFeedback={setFeedbackFor}
              onPublishNow={publishNow}
            />
            <Village topics={topics} />
          </div>
        </div>
      ) : (
        <>
          <LaneBar
            active={lane as StatusGroup}
            counts={counts}
            shown={matches.filter(t => lane === 'all' || statusMeta(t.status).group === lane).length}
            total={lane === 'all' ? topics.length : counts[lane as StatusGroup] ?? 0}
          />

          {/* The veto window is the one thing worth interrupting a lane for, and
              only on the lane that is about it. */}
          {lane === 'scheduled' && nextOut && (
            <div className="row wrap gap-22 mb-22" style={{ alignItems: 'flex-start' }}>
              <GoingOutNext
                topic={nextOut}
                onFeedback={setFeedbackFor}
                onPublishNow={publishNow}
              />
            </div>
          )}
        </>
      )}

      {groups.length === 0 ? (
        <EmptyState
          title="Nothing here"
          hint={query ? 'Try a different search.' : 'This lane is clear.'}
          action={
            <button type="button" className="btn btn--lav" onClick={() => setNewTopicOpen(true)}>
              Brief a new topic
            </button>
          }
        />
      ) : (
        groups.map((group, gi) => (
          <section key={group.key} style={{ marginBottom: 30 }} aria-label={group.label}>
            {/* On a single lane the bar above already names it and counts it;
                repeating it here is a heading that tells you nothing new. */}
            {groups.length > 1 && (
              <div className="row gap-12" style={{ marginBottom: 16, padding: '0 2px' }}>
                <span
                  className="dot dot--lg"
                  style={{ background: group.tone, color: group.tone }}
                  aria-hidden="true"
                />
                <h2 className="section-title" style={{ fontSize: 16 }}>{group.label}</h2>
                <span className="chip chip--grey">{group.items.length}</span>
              </div>
            )}
            <div className="grid-cards">
              {group.items.map((topic, i) => (
                <TopicCard key={topic.id} topic={topic} index={gi * 2 + Math.min(i, 6)} />
              ))}
            </div>
          </section>
        ))
      )}

      <NewTopicDialog
        open={newTopicOpen}
        onClose={() => setNewTopicOpen(false)}
        onCreated={upsertTopic}
      />
      <FeedbackDialog
        topic={feedbackFor}
        onClose={() => setFeedbackFor(null)}
        onSubmitted={refresh}
      />
    </div>
  )
}
