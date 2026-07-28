import { NextResponse } from 'next/server'
import { supabaseAdmin as supabase } from '../../../../../lib/supabase'

export const dynamic = 'force-dynamic'

const limit = (value: string, max: number) => {
  const clean = value.replace(/\s+/g, ' ').trim()
  return clean.length > max ? `${clean.slice(0, max - 1).trim()}…` : clean
}

const psQuote = (value: string) => `"${value.replace(/`/g, '``').replace(/"/g, '`"')}"`

export async function GET(_request: Request, context: { params: Promise<{ slug: string }> }) {
  const { slug } = await context.params

  const { data: topic, error: topicErr } = await supabase
    .from('topics')
    .select('*')
    .eq('slug', slug)
    .single()

  if (topicErr || !topic) {
    return NextResponse.json({ error: 'Topic not found' }, { status: 404 })
  }

  const { data: post } = await supabase
    .from('blog_posts')
    .select('*')
    .eq('topic_id', topic.id)
    .single()

  let digest: any = null
  try {
    digest = post?.research_json ? JSON.parse(post.research_json) : null
  } catch {}

  const title = limit(topic.title || 'Precision AI systems that ship work', 82)
  const subtitle = limit(
    digest?.summary ||
      digest?.what_people_say ||
      'No consultants. No pilot projects. Working systems.',
    130,
  )
  const angle = limit(
    digest?.buteforce_angle ||
      digest?.summary ||
      'Buteforce turns research, writing, humanising, and publishing into one controlled AI pipeline.',
    175,
  )
  const wordCount = post?.word_count ? `${post.word_count} words` : '8x'
  const props = {
    title,
    subtitle,
    angle,
    statOne: '12 min',
    statTwo: wordCount,
    cta: 'buteforce.com',
  }

  const baseArgs = [
    '--title',
    psQuote(props.title),
    '--subtitle',
    psQuote(props.subtitle),
    '--angle',
    psQuote(props.angle),
    '--statOne',
    psQuote(props.statOne),
    '--statTwo',
    psQuote(props.statTwo),
    '--cta',
    psQuote(props.cta),
  ].join(' ')

  return NextResponse.json({
    props,
    commands: {
      studio: 'npm run remotion:studio',
      vertical: `npm run remotion:render:topic -- --composition BlogPromo ${baseArgs} --out ${psQuote(`out/${slug}-story.mp4`)}`,
      landscape: `npm run remotion:render:topic -- --composition BlogLandscape ${baseArgs} --out ${psQuote(`out/${slug}-landscape.mp4`)}`,
    },
  })
}

