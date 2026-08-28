import type { Topic } from '../../lib/types'
import { statusMeta } from '../../lib/status'

/**
 * The ten agents and the two gates, and what each is doing right now.
 *
 * Every agent's state is derived from the real board — an agent is "working"
 * only because a topic is genuinely sitting in a status that agent owns. There
 * is no per-agent heartbeat in the database, and inventing one here would make
 * the most reassuring panel on the page the least trustworthy.
 *
 * The Imager is a permanent "Off": `ENABLE_IMAGES=false` and posts ship
 * text-only. Showing it as idle would hide a real configuration decision.
 */

interface AgentDef {
  name: string
  initial: string
  /** Topic statuses that mean this agent is executing. */
  statuses: readonly string[]
  /** What it does when nothing is in flight. */
  idle: string
  off?: boolean
}

const AGENTS: readonly AgentDef[] = [
  { name: 'Ideator',   initial: 'I', statuses: [],                       idle: 'Idle · fires only when the queue empties' },
  { name: 'Research',  initial: 'R', statuses: ['researching'],          idle: 'Idle · reads nine sources per topic' },
  { name: 'Auditor',   initial: 'A', statuses: ['verifying_research'],   idle: 'Idle · quality and fact gate' },
  { name: 'Writer',    initial: 'W', statuses: ['writing'],              idle: 'Idle · 1,400–2,000 words, length-gated' },
  { name: 'Humaniser', initial: 'H', statuses: ['writing'],              idle: 'Idle · strips the AI tells' },
  { name: 'Imager',    initial: 'M', statuses: [],                       idle: 'Off · ENABLE_IMAGES=false, posts ship text-only', off: true },
  { name: 'Linker',    initial: 'L', statuses: ['writing'],              idle: 'Idle · 2–4 validated backlinks' },
  { name: 'Schema',    initial: 'S', statuses: ['publishing'],           idle: 'Idle · Article + FAQPage JSON-LD' },
  { name: 'Social',    initial: 'C', statuses: ['publishing'],           idle: 'Idle · LinkedIn and X kit' },
  { name: 'Publisher', initial: 'P', statuses: ['publishing'],           idle: 'Idle · POSTs to the site API' },
]

const GATES = [
  { label: 'GEO gate',      sub: 'runs 3× per post',  tone: 'chip--lav' },
  { label: 'Length gate',   sub: '1,100-word floor',  tone: 'chip--lav' },
  { label: 'Link validator', sub: 'deterministic',    tone: 'chip--grey' },
]

export function Village({ topics }: { topics: readonly Topic[] }) {
  return (
    <section
      className="card rise"
      style={{ flex: '1.4 1 400px', minWidth: 320, '--i': 6 } as React.CSSProperties}
      aria-label="The village"
    >
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 6 }}>
        <h2 className="section-title" style={{ fontSize: 'var(--text-lg)' }}>The village</h2>
        <span className="t-sm" style={{ color: 'var(--ink-mute)' }}>Ten agents, two gates</span>
      </div>

      <ul style={{ listStyle: 'none' }}>
        {AGENTS.map(agent => {
          const working = topics.filter(t => agent.statuses.includes(t.status))
          const busy = !agent.off && working.length > 0
          const live = busy && agent.statuses.some(s => statusMeta(s).live)
          const tone = agent.off ? 'grey' : busy ? (live ? 'teal' : 'rose') : 'grey'
          const label = agent.off ? 'Off' : busy ? (live ? 'Working' : 'Needs you') : 'Idle'

          return (
            <li key={agent.name} className="hover-row row gap-14" style={{ padding: '10px 8px' }}>
              <span
                className={`display chip--${tone}`}
                style={{
                  width: 40, height: 40, flex: 'none',
                  borderRadius: 13,
                  display: 'grid', placeItems: 'center',
                  fontWeight: 600, fontSize: 15,
                }}
                aria-hidden="true"
              >
                {agent.initial}
              </span>

              <span style={{ minWidth: 0, flex: 1, lineHeight: 1.4 }}>
                <span style={{ display: 'block', fontWeight: 600, fontSize: 'var(--text-md)' }}>
                  {agent.name}
                </span>
                <span className="t-sm truncate" style={{ display: 'block', color: 'var(--ink-mute)' }}>
                  {busy ? working[0].title : agent.idle}
                </span>
              </span>

              <span className={`chip chip--${tone}`} style={{ flex: 'none' }}>
                <span className={`dot${live ? ' pulse pulse--fast' : ''}`} aria-hidden="true" />
                {label}
              </span>
            </li>
          )
        })}
      </ul>

      <div
        className="row wrap gap-10"
        style={{ padding: '16px 8px 0', marginTop: 8, borderTop: '1px solid var(--line-hair)' }}
      >
        <span className="t-sm" style={{ color: 'var(--ink-mute)' }}>Deterministic gates</span>
        {GATES.map(gate => (
          <span key={gate.label} className={`chip ${gate.tone}`}>
            {gate.label}
            {/* Weight, not `opacity: .72`. The chip already carries a tone
                colour, so alpha multiplied that down to 2.76:1 on the grey gates
                — a caption the operator is meant to read. Dropping to 500 while
                the label stays 600 keeps the same subordination, legibly. */}
            <span style={{ fontWeight: 500 }}>{gate.sub}</span>
          </span>
        ))}
      </div>
    </section>
  )
}
