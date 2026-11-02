import type { Reading } from '../../api/schemas'
import { Card } from './Card'

const NAMES = {
  attention_spike_no_substance: 'Buzz spike without real news',
  micro_cap: 'Very small company',
  price_spike: 'Big recent price jump',
  otc: 'Not on a major exchange',
  penny: 'Penny stock price',
  low_volume: 'Thinly traded',
} as const

export function HypeFlagsCard({ hype }: { hype: Reading['hype'] }) {
  const sorted = [...hype].sort((a, b) => Number(b.triggered) - Number(a.triggered))
  const any = hype.some((f) => f.triggered)
  return (
    <Card title="Hype check" className={any ? 'card-warn' : ''}>
      {!any && <p className="big-label ok">No warning signs</p>}
      <ul className="flags">
        {sorted.map((f) => (
          <li key={f.code} className={f.triggered ? 'flag-on' : 'flag-off'}>
            <span>{f.triggered ? '⚠︎' : '✓'} {NAMES[f.code]}</span>
            <span className="muted small">{f.value}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
