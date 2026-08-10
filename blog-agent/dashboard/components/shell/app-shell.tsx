'use client'

import { Suspense } from 'react'
import { usePathname } from 'next/navigation'
import { PipelineProvider } from '../../lib/pipeline-context'
import { ToastProvider } from '../ui/toast'
import { PointerSpotlight } from './pointer-spotlight'
import { Sidebar } from './sidebar'

/**
 * Chrome for the signed-in app.
 *
 * `/login` renders bare on purpose. The rail is navigation for a session that
 * does not exist yet, and — less cosmetically — the pipeline provider polls
 * `/api/topics`, which 401s without a session. Mounting it on the login page
 * would put the browser in a reload loop.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  if (pathname === '/login') {
    return <ToastProvider>{children}</ToastProvider>
  }

  return (
    <ToastProvider>
      <PipelineProvider>
        <a className="skip-link" href="#main">Skip to content</a>
        <PointerSpotlight />
        <div className="shell">
          {/* The rail reads `?lane=` and `?q=` from the URL, which makes it a
              search-params consumer and therefore a suspense boundary. */}
          <Suspense fallback={<div className="sidebar" aria-hidden="true" />}>
            <Sidebar />
          </Suspense>
          <main id="main" className="main" tabIndex={-1}>
            {children}
          </main>
        </div>
      </PipelineProvider>
    </ToastProvider>
  )
}
