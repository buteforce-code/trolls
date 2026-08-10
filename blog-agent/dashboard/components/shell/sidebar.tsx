'use client'

import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { useCallback, useEffect, useRef, useState } from 'react'
import { usePipeline } from '../../lib/pipeline-context'
import { useToast } from '../ui/toast'
import {
  BarsIcon, CheckCircleIcon, ChevronLeftIcon, ChevronRightIcon, ClockIcon, LearningIcon,
  PipelineIcon, ProgressIcon, ReviewIcon, SearchIcon, SignOutIcon, SwarmIcon, TrendIcon,
} from '../ui/icons'

const COLLAPSE_KEY = 'trolls.sidebar.collapsed'

interface LaneLink {
  lane: string
  label: string
  Icon: (p: { className?: string }) => React.ReactElement
  countKey: 'all' | 'attention' | 'progress' | 'scheduled' | 'published'
}

const LANES: LaneLink[] = [
  { lane: 'all',       label: 'Pipeline',     Icon: PipelineIcon,     countKey: 'all' },
  { lane: 'attention', label: 'Needs review', Icon: ReviewIcon,       countKey: 'attention' },
  { lane: 'progress',  label: 'In progress',  Icon: ProgressIcon,     countKey: 'progress' },
  { lane: 'scheduled', label: 'Scheduled',    Icon: ClockIcon,        countKey: 'scheduled' },
  { lane: 'published', label: 'Published',    Icon: CheckCircleIcon,  countKey: 'published' },
]

const ENGINE = [
  { href: '/swarm',       label: 'Swarm',          Icon: SwarmIcon },
  { href: '/performance', label: 'Performance',    Icon: TrendIcon },
  { href: '/learning',    label: 'Learning',       Icon: LearningIcon },
  { href: '/stats',       label: 'Pipeline stats', Icon: BarsIcon },
]

/**
 * The persistent left rail.
 *
 * It is the only navigation in the app, and it carries live counts because the
 * counts *are* the navigation: "Needs review 3" is both a label and the reason
 * to click it. Lanes are query params on `/` rather than separate routes, so a
 * filtered board is still a shareable URL and the back button behaves.
 */
export function Sidebar() {
  const pathname = usePathname()
  const params = useSearchParams()
  const router = useRouter()
  const { toast } = useToast()
  const { topics, counts } = usePipeline()

  const [collapsed, setCollapsed] = useState(false)
  const [query, setQuery] = useState('')
  const searchRef = useRef<HTMLInputElement>(null)

  // Restore the rail's width preference. Read after mount, never during render,
  // so the server and first client paint agree.
  useEffect(() => {
    try { setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === '1') } catch { /* private mode */ }
  }, [])

  const toggleCollapse = useCallback(() => {
    setCollapsed(prev => {
      const next = !prev
      try { window.localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0') } catch { /* private mode */ }
      return next
    })
  }, [])

  // Keep the field in step with the URL when the board is reached by a link.
  useEffect(() => { setQuery(params.get('q') ?? '') }, [params])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setCollapsed(false)
        searchRef.current?.focus()
        searchRef.current?.select()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  function submitSearch(value: string) {
    setQuery(value)
    const next = new URLSearchParams()
    if (value.trim()) next.set('q', value.trim())
    const lane = params.get('lane')
    if (lane && lane !== 'all') next.set('lane', lane)
    router.replace(`/${next.toString() ? `?${next}` : ''}`, { scroll: false })
  }

  async function signOut() {
    await fetch('/api/logout', { method: 'POST' })
    toast('Signed out')
    router.replace('/login')
    router.refresh()
  }

  const onBoard = pathname === '/'
  const activeLane = params.get('lane') ?? 'all'
  const countFor = (key: LaneLink['countKey']) =>
    key === 'all' ? topics.length : counts[key]

  const attention = counts.attention

  return (
    <aside
      className="sidebar"
      data-collapsed={collapsed}
      aria-label="Primary"
    >
      <Link href="/" className="brand">
        <span className="brand-mark" aria-hidden="true">
          <img src="/brand/bf-mark.png" alt="" width={23} height={23} />
        </span>
        <span className="collapsible">
          <span className="brand-name display">Trolls</span>
          <span className="brand-sub">Agent village</span>
        </span>
      </Link>

      <div className="search-wrap collapsible">
        <SearchIcon />
        <label htmlFor="topic-search" className="sr-only">Search topics</label>
        <input
          id="topic-search"
          ref={searchRef}
          className="search"
          type="search"
          value={query}
          placeholder="Search topics"
          onChange={e => submitSearch(e.target.value)}
        />
        <span className="kbd" aria-hidden="true">⌘K</span>
      </div>

      <nav aria-label="Pipeline lanes">
        <div className="side-label collapsible">Main menu</div>
        {LANES.map(({ lane, label, Icon, countKey }) => {
          const active = onBoard && activeLane === lane
          return (
            <Link
              key={lane}
              href={lane === 'all' ? '/' : `/?lane=${lane}`}
              className="nav-item"
              data-active={active}
              aria-current={active ? 'page' : undefined}
              /* The label and count are `display:none` whenever the rail is
                 collapsed — by the user's toggle, or automatically under 900px.
                 `display:none` removes them from the accessibility tree too, so
                 without this the whole nav becomes unlabelled icons. The name is
                 stated here so it survives every collapsed state. */
              aria-label={`${label}, ${countFor(countKey)}`}
              title={label}
            >
              <Icon />
              <span className="collapsible" aria-hidden="true">{label}</span>
              <span className="collapsible nav-badge" aria-hidden="true">{countFor(countKey)}</span>
            </Link>
          )
        })}
      </nav>

      <nav aria-label="Engine room">
        <div className="side-label collapsible">Engine room</div>
        {ENGINE.map(({ href, label, Icon }) => {
          const active = pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className="nav-item"
              data-active={active}
              aria-current={active ? 'page' : undefined}
              aria-label={label}
              title={label}
            >
              <Icon />
              <span className="collapsible" aria-hidden="true">{label}</span>
            </Link>
          )
        })}
      </nav>

      <div className="rail-spacer" />

      <div className="side-card collapsible">
        <div className="row gap-8" style={{ marginBottom: 7 }}>
          <span
            className="dot dot--lg pulse"
            style={{ background: 'var(--lav-ink)', color: 'var(--lav-ink)' }}
            aria-hidden="true"
          />
          <span className="side-card-title">{counts.progress ? 'Engine running' : 'Engine idle'}</span>
        </div>
        <p className="side-card-body">
          {attention
            ? `${attention} ${attention === 1 ? 'piece is' : 'pieces are'} waiting on your decision. Scheduled posts ship unless you step in.`
            : 'Nothing is waiting on you. Scheduled posts ship unless you step in.'}
        </p>
        <Link href="/?lane=attention" className="btn btn--lav btn--sm btn--block">
          {attention ? `Review ${attention} now` : 'Open the review lane'}
        </Link>
      </div>

      <button
        type="button"
        className="nav-item nav-item--collapse"
        onClick={toggleCollapse}
        aria-expanded={!collapsed}
        aria-label={collapsed ? 'Expand the sidebar' : 'Collapse the sidebar'}
      >
        {collapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
        <span className="collapsible" aria-hidden="true">Collapse</span>
      </button>
      <button type="button" className="nav-item" onClick={signOut} aria-label="Sign out">
        <SignOutIcon />
        <span className="collapsible" aria-hidden="true">Sign out</span>
      </button>
    </aside>
  )
}
