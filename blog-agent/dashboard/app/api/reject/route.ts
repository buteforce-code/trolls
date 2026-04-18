import { NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path from 'path'

export async function POST(request: Request) {
  const body = await request.json()
  const { slug, feedback } = body
  
  if (!slug || !feedback) {
    return NextResponse.json({ error: 'Slug and Feedback are required' }, { status: 400 })
  }
  
  const repoRoot = path.resolve(process.cwd(), '..')
  console.log(`Rejecting stage for topic: ${slug} with feedback`)
  
  const child = spawn('python', ['run.py', '--reject', slug, '--feedback', feedback], {
    cwd: repoRoot,
    detached: true,
    stdio: 'ignore'
  })
  
  child.unref()
  return NextResponse.json({ success: true })
}
