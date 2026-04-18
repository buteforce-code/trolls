import { NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path from 'path'

export async function POST(request: Request) {
  const body = await request.json()
  const { title, tags } = body
  
  if (!title) return NextResponse.json({ error: 'Title is required' }, { status: 400 })
  
  const tagsStr = Array.isArray(tags) ? tags.join(',') : tags || ''
  const repoRoot = path.resolve(process.cwd(), '..')
  
  console.log(`Starting run.py for topic: ${title}`)
  const child = spawn('python', ['run.py', '--topic', title, '--tags', tagsStr], {
    cwd: repoRoot,
    detached: true,
    stdio: 'inherit'
  })
  
  child.unref() 
  return NextResponse.json({ success: true })
}
