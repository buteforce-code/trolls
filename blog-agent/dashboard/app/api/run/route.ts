import { NextResponse } from 'next/server'
import { slugifyTopic, spawnPythonJob } from '../../../lib/python'

export async function POST(request: Request) {
  const body = await request.json()
  const { title, tags } = body
  
  if (!title) return NextResponse.json({ error: 'Title is required' }, { status: 400 })
  
  const tagsStr = Array.isArray(tags) ? tags.join(',') : tags || ''
  const slug = slugifyTopic(title)

  console.log(`Starting run.py for topic: ${title} (${slug})`)
  const { pid } = spawnPythonJob(['--topic', title, '--tags', tagsStr], `run:${slug}`)

  return NextResponse.json({ success: true, slug, pid })
}
