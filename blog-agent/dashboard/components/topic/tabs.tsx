'use client'

import { useRef } from 'react'

export interface TabDef {
  id: string
  label: string
  /** Rendered as a small count/marker after the label. */
  badge?: React.ReactNode
  disabled?: boolean
}

interface TabsProps {
  tabs: readonly TabDef[]
  active: string
  onChange: (id: string) => void
  label: string
}

/**
 * A real tablist, not a row of buttons that look like one.
 *
 * WAI-ARIA's tabs pattern is specific about keyboard behaviour and it is the
 * part that always gets dropped: only the selected tab is in the tab order, and
 * arrows move between them. Without that, reaching the sixth tab means six Tab
 * presses and the panel content is unreachable in between.
 */
export function Tabs({ tabs, active, onChange, label }: TabsProps) {
  const listRef = useRef<HTMLDivElement>(null)

  function onKeyDown(event: React.KeyboardEvent) {
    const enabled = tabs.filter(t => !t.disabled)
    const current = enabled.findIndex(t => t.id === active)
    if (current === -1) return

    let nextIndex: number | null = null
    if (event.key === 'ArrowRight') nextIndex = (current + 1) % enabled.length
    else if (event.key === 'ArrowLeft') nextIndex = (current - 1 + enabled.length) % enabled.length
    else if (event.key === 'Home') nextIndex = 0
    else if (event.key === 'End') nextIndex = enabled.length - 1
    if (nextIndex === null) return

    event.preventDefault()
    const next = enabled[nextIndex]
    onChange(next.id)
    listRef.current?.querySelector<HTMLElement>(`#tab-${next.id}`)?.focus()
  }

  return (
    <div ref={listRef} className="tabs" role="tablist" aria-label={label} onKeyDown={onKeyDown}>
      {tabs.map(tab => {
        const selected = tab.id === active
        return (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            type="button"
            role="tab"
            className="tab"
            aria-selected={selected}
            aria-controls={`panel-${tab.id}`}
            tabIndex={selected ? 0 : -1}
            disabled={tab.disabled}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
            {tab.badge}
          </button>
        )
      })}
    </div>
  )
}

export function TabPanel({ id, active, children }: { id: string; active: string; children: React.ReactNode }) {
  if (id !== active) return null
  return (
    <div
      id={`panel-${id}`}
      role="tabpanel"
      aria-labelledby={`tab-${id}`}
      tabIndex={0}
      className="view-enter"
    >
      {children}
    </div>
  )
}
