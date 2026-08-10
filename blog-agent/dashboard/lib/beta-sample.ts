/**
 * A real Beta sampler, for the "draw from the posteriors" control.
 *
 * The point of that control is to show that a wide, uncertain arm sometimes
 * beats a confident one on luck alone — that is exploration, and it is the
 * mechanism the whole learning layer rests on. A fake draw (uniform noise, or
 * always picking the highest mean) would demonstrate the opposite of the thing
 * it exists to demonstrate, so this is Marsaglia–Tsang gamma sampling, the same
 * method `swarm/learning/bandit.py` uses on the Python side.
 *
 * Beta(a, b) is drawn as X / (X + Y) where X ~ Gamma(a, 1) and Y ~ Gamma(b, 1).
 */

/** Box–Muller standard normal. */
function normal(): number {
  let u = 0
  let v = 0
  while (u === 0) u = Math.random()
  while (v === 0) v = Math.random()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

function gamma(shape: number): number {
  // Marsaglia–Tsang requires shape >= 1; below that, boost and correct.
  if (shape < 1) return gamma(1 + shape) * Math.pow(Math.random() || 1e-9, 1 / shape)

  const d = shape - 1 / 3
  const c = 1 / Math.sqrt(9 * d)

  for (let attempt = 0; attempt < 200; attempt += 1) {
    let x = 0
    let v = 0
    do {
      x = normal()
      v = 1 + c * x
    } while (v <= 0)
    v = v * v * v

    const u = Math.random()
    if (u < 1 - 0.0331 * x * x * x * x) return d * v
    if (Math.log(u || 1e-9) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v
  }
  // The rejection loop effectively always returns well before 200 attempts;
  // the mode is a safe, unbiased-enough fallback rather than an infinite loop.
  return d
}

export function sampleBeta(alpha: number, beta: number): number {
  const a = Math.max(1e-6, alpha)
  const b = Math.max(1e-6, beta)
  const x = gamma(a)
  const y = gamma(b)
  return x / (x + y || 1)
}
