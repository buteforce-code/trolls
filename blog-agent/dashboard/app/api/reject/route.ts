import { NextResponse } from 'next/server'
import { spawnPythonJob } from '../../../lib/python'

export async function POST(request: Request) {
  const body = await request.json()
  const { slug, feedback } = body
  
  if (!slug || !feedback) {
    return NextResponse.json({ error: 'Slug and Feedback are required' }, { status: 400 })
  }
  
  console.log(`Rejecting stage for topic: ${slug} with feedback`)

  const { pid } = spawnPythonJob(['--reject', slug, '--feedback', feedback || ''], `reject:${slug}`, slug)
  return NextResponse.json({ success: true, pid })
}
