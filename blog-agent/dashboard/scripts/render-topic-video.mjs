import path from 'node:path'
import { mkdir } from 'node:fs/promises'
import { bundle } from '@remotion/bundler'
import { getCompositions, renderMedia } from '@remotion/renderer'

const args = new Map()
for (let i = 2; i < process.argv.length; i += 2) {
  const key = process.argv[i]
  const value = process.argv[i + 1]
  if (!key?.startsWith('--') || typeof value === 'undefined') continue
  args.set(key.slice(2), value)
}

const compositionId = args.get('composition') || 'BlogPromo'
const inputProps = {
  title: args.get('title') || 'Precision AI systems that ship work',
  subtitle: args.get('subtitle') || 'No consultants. No pilot projects. Working systems.',
  angle:
    args.get('angle') ||
    'Buteforce turns research, writing, humanising, and publishing into one controlled AI pipeline.',
  statOne: args.get('statOne') || '12 min',
  statTwo: args.get('statTwo') || '8x',
  cta: args.get('cta') || 'buteforce.com',
}

const outputLocation =
  args.get('out') ||
  path.resolve(process.cwd(), 'out', `${compositionId.toLowerCase()}-${Date.now()}.mp4`)

await mkdir(path.dirname(outputLocation), { recursive: true })

const entryPoint = path.resolve(process.cwd(), 'remotion', 'index.ts')
const serveUrl = await bundle({ entryPoint })
const compositions = await getCompositions(serveUrl, { inputProps })
const composition = compositions.find((item) => item.id === compositionId)

if (!composition) {
  throw new Error(`Unknown composition "${compositionId}". Available: ${compositions.map((c) => c.id).join(', ')}`)
}

console.log(`Rendering ${compositionId} to ${outputLocation}`)
await renderMedia({
  composition,
  serveUrl,
  codec: 'h264',
  outputLocation,
  inputProps,
})
console.log(`Rendered ${outputLocation}`)

