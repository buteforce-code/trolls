/**
 * The icon set, exactly as drawn in the v4 design.
 *
 * All 24×24, all stroked at 1.9 with `currentColor`, all sized by CSS rather
 * than props — so an icon inside a button inherits the button's colour and an
 * icon inside a nav item inherits the nav item's active state for free.
 *
 * Icons are decoration: every one is `aria-hidden`, and the control that holds
 * it carries the accessible name.
 */

interface IconProps {
  className?: string
  style?: React.CSSProperties
}

function svg(children: React.ReactNode) {
  return function Icon({ className, style }: IconProps) {
    return (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        focusable="false"
        className={className}
        style={style}
      >
        {children}
      </svg>
    )
  }
}

export const PipelineIcon = svg(
  <>
    <rect x="3" y="4" width="18" height="6" rx="2.5" />
    <rect x="3" y="14" width="11" height="6" rx="2.5" />
  </>,
)

export const ReviewIcon = svg(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v4" />
    <circle cx="12" cy="16" r="0.7" fill="currentColor" />
  </>,
)

export const ProgressIcon = svg(<path d="M3 12h4l2 6 4-14 2 8h6" />)

export const ClockIcon = svg(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.5v5l3 2" />
  </>,
)

export const CheckCircleIcon = svg(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M8.5 12.5l2.5 2.5 4.5-5" />
  </>,
)

export const SwarmIcon = svg(
  <>
    <circle cx="12" cy="12" r="2.6" />
    <circle cx="5" cy="6" r="2" />
    <circle cx="19" cy="6" r="2" />
    <circle cx="5" cy="18" r="2" />
    <circle cx="19" cy="18" r="2" />
    <path d="M6.6 7.4l3.6 3.2M17.4 7.4l-3.6 3.2M6.6 16.6l3.6-3.2M17.4 16.6l-3.6-3.2" />
  </>,
)

export const TrendIcon = svg(
  <>
    <path d="M3 17l5.5-6 4 3.5L21 6" />
    <path d="M16 6h5v5" />
  </>,
)

export const LearningIcon = svg(
  <>
    <path d="M4 18c3-9 13-9 16 0" />
    <path d="M4 18h16" />
    <circle cx="12" cy="8.6" r="1.4" fill="currentColor" stroke="none" />
  </>,
)

export const BarsIcon = svg(<path d="M4 20V11M10 20V4M16 20v-6M22 20H2" />)

export const SearchIcon = svg(
  <>
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4-4" />
  </>,
)

export const BellIcon = svg(
  <>
    <path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.7 21a2 2 0 01-3.4 0" />
  </>,
)

export const PlusIcon = svg(<path d="M12 5v14M5 12h14" strokeWidth="2.3" />)

export const SignOutIcon = svg(
  <>
    <path d="M15 17l5-5-5-5" />
    <path d="M20 12H9" />
    <path d="M11 4H6a2 2 0 00-2 2v12a2 2 0 002 2h5" />
  </>,
)

export const ChevronLeftIcon = svg(<path d="M15 6l-6 6 6 6" />)
export const ChevronRightIcon = svg(<path d="M9 6l6 6-6 6" />)
export const ArrowLeftIcon = svg(<path d="M19 12H5M11 6l-6 6 6 6" />)

export const CopyIcon = svg(
  <>
    <rect x="9" y="9" width="11" height="11" rx="2.5" />
    <path d="M6 15H5a1 1 0 01-1-1V5a1 1 0 011-1h9a1 1 0 011 1v1" />
  </>,
)

export const TrashIcon = svg(
  <>
    <path d="M4 7h16" />
    <path d="M9 7V5a1 1 0 011-1h4a1 1 0 011 1v2" />
    <path d="M6 7l1 12a2 2 0 002 2h6a2 2 0 002-2l1-12" />
  </>,
)

export const RefreshIcon = svg(
  <>
    <path d="M20 11a8 8 0 10-2.3 6.3" />
    <path d="M20 5v6h-6" />
  </>,
)
