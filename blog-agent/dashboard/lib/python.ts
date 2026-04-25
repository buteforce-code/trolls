import { spawn } from 'child_process'
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

export function spawnPythonJob(args: string[], label: string): { pid: number | undefined } {
  const repoRoot = path.resolve(process.cwd(), '..')
  const child = spawn('python', ['run.py', ...args], {
    cwd: repoRoot,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  child.stdout.on('data', chunk => {
    const text = chunk.toString().trimEnd()
    if (text) console.log(`[python:${label}] ${text}`)
  })

  child.stderr.on('data', chunk => {
    const text = chunk.toString().trimEnd()
    if (text) console.error(`[python:${label}] ${text}`)
  })

  child.on('spawn', () => {
    console.log(`[python:${label}] started pid=${child.pid ?? 'unknown'}`)
  })

  child.on('error', err => {
    console.error(`[python:${label}] failed to start: ${err.message}`)
  })

  child.on('close', code => {
    console.log(`[python:${label}] exited code=${code ?? 'unknown'}`)
  })

  return { pid: child.pid }
}
