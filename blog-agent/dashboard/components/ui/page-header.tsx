interface PageHeaderProps {
  title: string
  subtitle?: React.ReactNode
  /** Right-hand controls: filters, primary action, account. */
  actions?: React.ReactNode
  /** The aurora + sheen treatment. On by default; off for dense sub-pages. */
  ambient?: boolean
}

/**
 * Every view opens the same way: a display-face title over a one-line statement
 * of what the numbers below actually mean, with a soft aurora behind it.
 *
 * The aurora is the app's only decorative element. It is `aria-hidden`, sits at
 * z-index 0 under live text, and is removed entirely under reduced motion.
 */
export function PageHeader({ title, subtitle, actions, ambient = true }: PageHeaderProps) {
  return (
    <header className="page-head rise">
      {ambient && <div className="aurora" aria-hidden="true" />}
      <div className="page-head-row">
        <div style={{ position: 'relative', minWidth: 0 }}>
          <h1 className={ambient ? 'sheen' : undefined}>{title}</h1>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {actions && <div className="row wrap gap-12">{actions}</div>}
      </div>
    </header>
  )
}

interface EmptyStateProps {
  title: string
  hint?: React.ReactNode
  action?: React.ReactNode
}

/** The shape shown when a lane, a chart or a table has nothing in it yet. */
export function EmptyState({ title, hint, action }: EmptyStateProps) {
  return (
    <div className="empty">
      <p style={{ fontWeight: 600, color: 'var(--ink)' }}>{title}</p>
      {hint && <p style={{ marginTop: 8, maxWidth: '52ch', marginInline: 'auto' }}>{hint}</p>}
      {action && <div style={{ marginTop: 18 }}>{action}</div>}
    </div>
  )
}
