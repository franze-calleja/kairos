import { useState } from 'react'
import type { Reading } from '../../api/schemas'
import { Card } from './Card'

// Warning wording only when a flag is triggered; passed checks get a neutral label.
const WARNINGS = {
  attention_spike_no_substance: 'Buzz spike without real news',
  micro_cap: 'Very small company',
  price_spike: 'Big recent price jump',
  otc: 'Not on a major exchange',
  penny: 'Penny stock price',
  low_volume: 'Thinly traded',
} as const

const CHECKS = {
  attention_spike_no_substance: 'Buzz vs. real news',
  micro_cap: 'Company size',
  price_spike: '5-day price move',
  otc: 'Exchange',
  penny: 'Share price',
  low_volume: 'Trading volume',
} as const

export function HypeFlagsCard({ hype }: { hype: Reading['hype'] }) {
  const any = hype.some((f) => f.triggered)
  const [open, setOpen] = useState(false)
  const sorted = [...hype].sort((a, b) => Number(b.triggered) - Number(a.triggered))
  const showList = any || open
  return (
    <Card title="Hype check" className={any ? 'card-warn' : ''}>
      {!any && (
        <p className="big-label ok">
          No warning signs{' '}
          <button type="button" className="link-button small" aria-expanded={open} onClick={() => setOpen(!open)}>
            {hype.length} checks passed {open ? '▾' : '▸'}
          </button>
        </p>
      )}
      {showList && (
        <ul className="flags">
          {sorted.map((f) => (
            <li key={f.code} className={f.triggered ? 'flag-on' : 'flag-off'}>
              <span>{f.triggered ? `⚠︎ ${WARNINGS[f.code]}` : `✓ ${CHECKS[f.code]}`}</span>
              <span className="muted small">{f.value}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
