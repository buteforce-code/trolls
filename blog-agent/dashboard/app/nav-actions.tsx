'use client'

import { useRouter } from 'next/navigation'
import { usePathname } from 'next/navigation'

/**
 * Nav links plus sign-out.
 *
 * Split into a client component so the layout itself can stay a server
 * component. The login page renders no nav actions — offering "Sign out" to
 * someone who is not signed in reads as a bug.
 */
export default function NavActions() {
  const router = useRouter()
  const pathname = usePathname()

  if (pathname === '/login') return null

  async function signOut() {
    await fetch('/api/logout', { method: 'POST' })
    router.replace('/login')
    router.refresh()
  }

  return (
    <div className="nav-actions">
      <a className={`nav-link${pathname === '/' ? ' is-active' : ''}`} href="/">Topics</a>
      <a className={`nav-link${pathname.startsWith('/swarm') ? ' is-active' : ''}`} href="/swarm">Swarm</a>
      <a className={`nav-link${pathname.startsWith('/stats') ? ' is-active' : ''}`} href="/stats">Pipeline</a>
      <a className={`nav-link${pathname.startsWith('/performance') ? ' is-active' : ''}`} href="/performance">Performance</a>
      <a className={`nav-link${pathname.startsWith('/learning') ? ' is-active' : ''}`} href="/learning">Learning</a>
      <button className="nav-link nav-signout" onClick={signOut} type="button">Sign out</button>
    </div>
  )
}
