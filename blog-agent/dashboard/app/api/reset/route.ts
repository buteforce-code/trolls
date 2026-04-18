import { NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path from 'path'

export async function POST(request: Request) {
  const body = await request.json()
  const { slug } = body
  if (!slug) return NextResponse.json({ error: 'Slug is required' }, { status: 400 })

  const repoRoot = path.resolve(process.cwd(), '..')
  const child = spawn('python', ['run.py', '--reset', slug], {
    cwd: repoRoot,
    detached: true,
    stdio: 'ignore',
  })
  child.unref()

  return NextResponse.json({ success: true })
}
