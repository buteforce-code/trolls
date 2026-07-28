'use client'

import { Suspense, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

/**
 * `useSearchParams` opts the subtree into client-side rendering, so it must sit
 * behind a Suspense boundary or the production build fails while prerendering
 * this route. The boundary lives here rather than in the layout so only the
 * form waits, not the whole page frame.
 */
export default function LoginPage() {
  return (
    <Suspense fallback={<main className="login-wrap"><div className="login-card" /></main>}>
      <LoginForm />
    </Suspense>
  )
}

function LoginForm() {
  const router = useRouter()
  const params = useSearchParams()
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setError(data.error || 'Sign-in failed.')
        setBusy(false)
        return
      }
      // Only same-origin paths are accepted, so a crafted ?next=https://evil...
      // cannot turn the login form into an open redirect.
      const next = params.get('next')
      const safeNext = next && next.startsWith('/') && !next.startsWith('//') ? next : '/'
      router.replace(safeNext)
      router.refresh()
    } catch {
      setError('Could not reach the server.')
      setBusy(false)
    }
  }

  return (
    <main className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <h1 className="login-title">Trolls</h1>
        <p className="login-sub">Marketing agent swarm — operator sign-in</p>

        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            autoFocus
            autoComplete="current-password"
            onChange={e => setPassword(e.target.value)}
            placeholder="Operator password"
          />
        </div>

        {error ? <p className="login-error" role="alert">{error}</p> : null}

        <button className="btn btn-primary" type="submit" disabled={busy || !password}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  )
}
