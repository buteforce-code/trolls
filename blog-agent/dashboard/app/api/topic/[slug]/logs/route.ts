import { NextResponse } from 'next/server'
import fs from 'fs'
import { jobLogPath } from '../../../../../lib/python'

export const dynamic = 'force-dynamic'

const SLUG_RE = /^[a-z0-9-]+$/

export async function GET(request: Request, context: { params: Promise<{ slug: string }> }) {
  const { slug } = await context.params

  if (!SLUG_RE.test(slug)) {
    return NextResponse.json({ error: 'Invalid slug' }, { status: 400 })
  }

  const url = new URL(request.url)
  const after = Math.max(0, parseInt(url.searchParams.get('after') || '0', 10) || 0)
  const tail = Math.max(0, parseInt(url.searchParams.get('tail') || '0', 10) || 0)

  const logPath = jobLogPath(slug)

  let stat: fs.Stats
  try {
    stat = await fs.promises.stat(logPath)
  } catch {
    return NextResponse.json({ exists: false, lines: [], totalBytes: 0 })
  }

  const totalBytes = stat.size
  const startByte = tail > 0 ? Math.max(0, totalBytes - tail) : Math.min(after, totalBytes)

  if (startByte >= totalBytes) {
    return NextResponse.json({ exists: true, lines: [], totalBytes, mtime: stat.mtimeMs })
  }

  const fd = await fs.promises.open(logPath, 'r')
  try {
    const buf = Buffer.alloc(totalBytes - startByte)
    await fd.read(buf, 0, buf.length, startByte)
    const text = buf.toString('utf8')
    const lines = text.split('\n').filter(l => l.length > 0)
    return NextResponse.json({ exists: true, lines, totalBytes, mtime: stat.mtimeMs })
  } finally {
    await fd.close()
  }
}
