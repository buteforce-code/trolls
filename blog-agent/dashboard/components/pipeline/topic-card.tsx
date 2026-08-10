import Link from 'next/link'
import type { Topic } from '../../lib/types'
import { relative, untilShort } from '../../lib/format'
import { StatusChip, Tag } from '../ui/chip'

/**
 * One topic on the board.
 *
 * The whole card is the link. The previous version put a delete "×" inside the
 * card and had to fight it with `preventDefault`/`stopPropagation` on every
 * click, which made the primary action — open the topic — the thing most likely
 * to be missed. Deletion now lives on the topic's own page, one deliberate step
 * further from the cursor.
 */
export function TopicCard({ topic, index }: { topic: Topic; index: number }) {
  const scheduled = topic.status === 'scheduled' && topic.scheduled_for

  return (
    <Link
      href={`/topic/${topic.slug}`}
      className="card card--interactive rise"
      style={{
        padding: '20px 22px',
        borderRadius: 'var(--r-xl)',
        display: 'flex',
        flexDirection: 'column',
        gap: 13,
        '--i': index,
      } as React.CSSProperties}
    >
      <span className="row gap-10" style={{ justifyContent: 'space-between' }}>
        <StatusChip status={topic.status} />
        <span className="t-sm faint" style={{ whiteSpace: 'nowrap' }}>
          {scheduled ? untilShort(topic.scheduled_for) : relative(topic.updated_at)}
        </span>
      </span>

      <span
        className="pretty"
        style={{ fontWeight: 600, fontSize: '15.5px', lineHeight: 1.45, letterSpacing: '-.01em' }}
      >
        {topic.title}
      </span>

      {(topic.tags?.length ?? 0) > 0 && (
        <span className="row wrap gap-6" style={{ marginTop: 'auto' }}>
          {topic.tags!.slice(0, 4).map(tag => <Tag key={tag}>{tag}</Tag>)}
        </span>
      )}
    </Link>
  )
}
