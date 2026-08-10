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

// `path.join` collapses `..` segments, so a slug arriving here unvalidated
// (as it does from /api/approve, /api/delete, /api/reject and /api/reset,
// which take it straight from the request body) can write a log file outside
// LOG_DIR — an authenticated arbitrary-file-write primitive, `.log`-suffixed
// but otherwise attacker-shaped. `/api/topic/[slug]/logs` already validates
// its own slug before calling this; enforcing the same shape here protects
// every caller, present and future, at the one place the path is built.
const SAFE_SLUG_RE = /^[a-z0-9-]+$/

export function jobLogPath(slug: string): string {
  if (!SAFE_SLUG_RE.test(slug)) {
    throw new Error(`refusing to build a log path from an unsafe slug: ${JSON.stringify(slug)}`)
  }
  return path.join(LOG_DIR, `${slug}.log`)
}

// Which interpreter to spawn. Bare `python` exists on Windows and on Render's
// image, but not on a Debian container, where only `python3` is on PATH and a
// virtualenv's interpreter is somewhere else entirely. Hardcoding `python`
// turns a missing interpreter into an ENOENT at job time — a failure that looks
// like an application bug rather than a deployment one. Hosts set PYTHON_BIN.
const PYTHON_BIN = process.env.PYTHON_BIN || 'python'

export function spawnPythonJob(args: string[], label: string, slug?: string): { pid: number | undefined } {
  const repoRoot = path.resolve(process.cwd(), '..')
  const child = spawn(PYTHON_BIN, ['run.py', ...args], {
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
