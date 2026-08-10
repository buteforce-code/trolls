'use client'

import { CopyButton } from '../ui/copy-button'
import { EmptyState } from '../ui/page-header'

/**
 * The social kit, exactly as the social agent produced it.
 *
 * The shape is nested and partially optional — a run can produce LinkedIn posts
 * and no X thread, or a carousel with no title. Everything here is defensive:
 * a block that is missing is simply not rendered, because the alternative
 * (rendering an empty card labelled "Contrarian Take") reads as a broken
 * generation rather than one that was never asked for.
 */

export interface SocialKit {
  linkedin?: {
    founder_story?: string
    contrarian?: string
    data_post?: string
    bilateral?: string
    company_page?: string
    carousel?: { title?: string; slides?: string[] }
  }
  x?: {
    thread_numbered?: string[]
    thread_story_or_howto?: string[]
    tweets?: string[]
  }
  hashtags?: { linkedin?: string[]; x?: string[] }
  first_comment_link?: string
}

interface Block {
  kind: string
  meta: string
  text: string
  channel: 'linkedin' | 'x' | 'other'
}

function buildBlocks(kit: SocialKit): Block[] {
  const blocks: Block[] = []
  const li = kit.linkedin
  const x = kit.x

  if (li?.carousel?.slides?.length) {
    blocks.push({
      kind: 'LinkedIn carousel',
      meta: `${li.carousel.slides.length} slides${li.carousel.title ? ` · ${li.carousel.title}` : ''}`,
      text: li.carousel.slides.map((s, i) => `${i + 1}. ${s}`).join('\n'),
      channel: 'linkedin',
    })
  }
  const liPosts: [string, string | undefined][] = [
    ['Founder story', li?.founder_story],
    ['Contrarian take', li?.contrarian],
    ['Data post', li?.data_post],
    ['Bilateral / corridor', li?.bilateral],
    ['Company page post', li?.company_page],
  ]
  for (const [kind, text] of liPosts) {
    if (text) blocks.push({ kind: `LinkedIn · ${kind}`, meta: `${text.length} chars`, text, channel: 'linkedin' })
  }

  if (x?.thread_numbered?.length) {
    blocks.push({
      kind: 'X thread',
      meta: `${x.thread_numbered.length} posts`,
      text: x.thread_numbered.join('\n\n'),
      channel: 'x',
    })
  }
  if (x?.thread_story_or_howto?.length) {
    blocks.push({
      kind: 'X thread · story / how-to',
      meta: `${x.thread_story_or_howto.length} posts`,
      text: x.thread_story_or_howto.join('\n\n'),
      channel: 'x',
    })
  }
  if (x?.tweets?.length) {
    blocks.push({ kind: 'X posts', meta: `${x.tweets.length} single`, text: x.tweets.join('\n\n'), channel: 'x' })
  }

  if (kit.hashtags?.linkedin?.length || kit.hashtags?.x?.length) {
    blocks.push({
      kind: 'Hashtags',
      meta: 'copy block',
      text: [
        kit.hashtags.linkedin?.length ? `LinkedIn: ${kit.hashtags.linkedin.join(' ')}` : '',
        kit.hashtags.x?.length ? `X: ${kit.hashtags.x.join(' ')}` : '',
      ].filter(Boolean).join('\n'),
      channel: 'other',
    })
  }
  if (kit.first_comment_link) {
    blocks.push({ kind: 'First comment', meta: 'the link', text: kit.first_comment_link, channel: 'other' })
  }

  return blocks
}

export function SocialPanel({ kit }: { kit: SocialKit | null }) {
  const blocks = kit ? buildBlocks(kit) : []

  if (blocks.length === 0) {
    return (
      <EmptyState
        title="No social kit yet"
        hint="The social agent generates the LinkedIn and X assets once the draft is approved."
      />
    )
  }

  return (
    <>
      <p className="t-base muted mb-18">Click any block to copy it.</p>
      {blocks.map(block => (
        <article key={block.kind} style={{ marginBottom: 16 }}>
          <div className="row wrap gap-10" style={{ marginBottom: 8 }}>
            <span className={`chip ${block.channel === 'linkedin' ? 'chip--lav' : 'chip--grey'}`}>
              {block.kind}
            </span>
            <span className="t-sm faint">{block.meta}</span>
            <CopyButton text={block.text} label={block.kind} className="btn btn--ghost btn--xs push" />
          </div>
          <pre
            className="code"
            style={{ fontFamily: 'var(--font-sans)', fontSize: 'var(--text-base)', lineHeight: 1.7 }}
          >
            {block.text}
          </pre>
        </article>
      ))}
    </>
  )
}
