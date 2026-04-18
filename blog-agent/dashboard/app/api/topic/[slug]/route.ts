import { NextResponse } from 'next/server'
import { supabase } from '../../../../lib/supabase'

export const dynamic = 'force-dynamic'

export async function GET(request: Request, context: { params: Promise<{ slug: string }> }) {
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

  return NextResponse.json({ topic, post: post || null })
}
