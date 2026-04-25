import { NextResponse } from 'next/server'
import { spawnPythonJob } from '../../../lib/python'

export async function POST(request: Request) {
  const body = await request.json()
  const { slug } = body
  
  if (!slug) return NextResponse.json({ error: 'Slug is required' }, { status: 400 })
  
  console.log(`Approving stage for topic: ${slug}`)

  const { pid } = spawnPythonJob(['--approve', slug], `approve:${slug}`)
  return NextResponse.json({ success: true, pid })
}
