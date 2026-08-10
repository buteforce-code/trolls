'use client'

import { useState } from 'react'
import { useToast } from './toast'

interface CopyButtonProps {
  text: string
  /** What was copied, for the toast: "MDX copied". */
  label?: string
  children?: React.ReactNode
  className?: string
}

/**
 * Copy-to-clipboard with an honest failure path.
 *
 * `navigator.clipboard` is unavailable on insecure origins and can be denied by
 * permission policy. The old implementation swallowed that in a bare try/catch,
 * so a click did nothing and said nothing. Here the failure is surfaced and the
 * text is left selected for a manual copy.
 */
export function CopyButton({ text, label = 'Block', children, className = 'btn btn--ghost btn--xs' }: CopyButtonProps) {
  const { toast } = useToast()
  const [done, setDone] = useState(false)

  async function copy() {
    try {
      if (!navigator.clipboard) throw new Error('clipboard unavailable')
      await navigator.clipboard.writeText(text)
      setDone(true)
      setTimeout(() => setDone(false), 1600)
      toast(`${label} copied`)
    } catch {
      toast(`Could not copy — select the text and press Ctrl+C`, 'error')
    }
  }

  return (
    <button type="button" className={className} onClick={copy}>
      {children ?? (done ? 'Copied' : 'Copy')}
    </button>
  )
}
