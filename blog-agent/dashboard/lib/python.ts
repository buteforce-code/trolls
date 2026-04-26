import { spawn } from 'child_process'
import fs from 'fs'
import os from 'os'
import path from 'path'

export function slugifyTopic(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
}

const LOG_DIR = path.join(os.tmpdir(), 'blog-agent-jobs')

export function jobLogPath(slug: string): string {
  return path.join(LOG_DIR, `${slug}.log`)
}

export function spawnPythonJob(args: string[], label: string, slug?: string): { pid: number | undefined } {
  const repoRoot = path.resolve(process.cwd(), '..')
  const child = spawn('python', ['run.py', ...args], {
    cwd: repoRoot,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  let logStream: fs.WriteStream | null = null
  if (slug) {
    try {
      fs.mkdirSync(LOG_DIR, { recursive: true })
      logStream = fs.createWriteStream(jobLogPath(slug), { flags: 'w' })
      logStream.write(`[${new Date().toISOString()}] [spawn] label=${label} args=${JSON.stringify(args)}\n`)
    } catch (err) {
      console.error(`[python:${label}] log file open failed: ${(err as Error).message}`)
    }
  }

  const writeLog = (text: string, isErr: boolean) => {
    if (!text) return
    if (isErr) console.error(`[python:${label}] ${text}`)
    else console.log(`[python:${label}] ${text}`)
    if (logStream) {
      try {
        logStream.write(`[${new Date().toISOString()}]${isErr ? ' [stderr]' : ''} ${text}\n`)
      } catch {}
    }
  }

  child.stdout.on('data', chunk => writeLog(chunk.toString().trimEnd(), false))
  child.stderr.on('data', chunk => writeLog(chunk.toString().trimEnd(), true))

  child.on('spawn', () => {
    writeLog(`started pid=${child.pid ?? 'unknown'}`, false)
  })

  child.on('error', err => {
    writeLog(`failed to start: ${err.message}`, true)
  })

  child.on('close', code => {
    writeLog(`exited code=${code ?? 'unknown'}`, false)
    if (logStream) {
      try { logStream.end() } catch {}
    }
  })

  return { pid: child.pid }
}
