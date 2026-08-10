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
      // Only a same-origin, single-segment-rooted path is accepted.
      // startsWith('/') alone is not enough: browsers (and Next's own
      // client router, which resolves this href through the URL parser)
      // strip embedded tab/CR/LF bytes while parsing a URL, so a value
      // shaped like a slash, a raw tab, another slash, then evil.com reads
      // as safe by that check alone but resolves to a protocol-relative
      // double-slash address - an off-origin redirect. Walking the string
      // and rejecting any ASCII control code point (0 through 31) or a
      // literal backslash (code 92, which browsers also fold into a
      // forward slash) closes that class of bypass.
      const next = params.get('next')
      const BACKSLASH_CODE = 92
      const isSafeNext = (value: string): boolean => {
        if (!value.startsWith('/') || value.startsWith('//')) return false
        for (let i = 0; i < value.length; i += 1) {
          const code = value.charCodeAt(i)
          if (code <= 31 || code === BACKSLASH_CODE) return false
        }
        return true
      }
      const safeNext = next && isSafeNext(next) ? next : '/'
      router.replace(safeNext)
      router.refresh()
    } catch {
      setError('Could not reach the server.')
      setBusy(false)
    }
  }

  return (
    <main className="login-wrap">
      <div className="aurora" style={{ width: 420, height: 300, left: '50%', top: '18%', marginLeft: -210 }} aria-hidden="true" />

      <form className="login-card rise" onSubmit={submit}>
        <div className="row gap-12">
          <span className="brand-mark" aria-hidden="true">
            <img src="/brand/bf-mark.png" alt="" width={23} height={23} />
          </span>
          <span>
            <h1 className="brand-name display" style={{ display: 'block', margin: 0 }}>Trolls</h1>
            <span className="brand-sub">Agent village</span>
          </span>
        </div>

        <p className="dialog-body">
          Ten agents research, write and humanise; two deterministic gates decide what is
          allowed to ship. Sign in to steer it.
        </p>

        <div>
          <label className="field-label" htmlFor="password">Operator password</label>
          <input
            id="password"
            className="input"
            type="password"
            value={password}
            autoFocus
            autoComplete="current-password"
            onChange={e => setPassword(e.target.value)}
            placeholder="••••••••••••"
            aria-describedby={error ? 'login-error' : undefined}
            aria-invalid={error ? true : undefined}
          />
        </div>

        {error && (
          <p id="login-error" className="notice notice--rose t-base" role="alert">{error}</p>
        )}

        <button className="btn btn--primary btn--block" type="submit" disabled={busy || !password}>
          {busy ? <><span className="spinner" /> Signing in…</> : 'Sign in'}
        </button>
      </form>
    </main>
  )
}
