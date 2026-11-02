import type { Reading } from '../../api/schemas'
import { pct } from '../format'
import { Card } from './Card'

const LABELS = {
  stretched: 'Stretched above its averages',
  near_average: 'Near its long-term average',
  below_range: 'Well below its recent range',
  insufficient_history: 'Not enough price history',
} as const

export function AddMoreCard({ price }: { price: NonNullable<Reading['price']> }) {
  return (
    <Card title="Should I add more?">
      <p className="big-label">{LABELS[price.label]}</p>
      <dl className="stats">
        <dt>vs 50-day avg</dt>
        <dd>{pct(price.pct_vs_ma50)}</dd>
        <dt>vs 200-day avg</dt>
        <dd>{pct(price.pct_vs_ma200)}</dd>
        <dt>From 52-week high</dt>
        <dd>{pct(price.pct_from_52w_high)}</dd>
        <dt>52-week range</dt>
        <dd>
          ${price.low_52w.toFixed(2)} – ${price.high_52w.toFixed(2)}
        </dd>
        <dt>30-day volatility</dt>
        <dd>{price.volatility_30d === null ? '—' : `${price.volatility_30d.toFixed(0)}% / yr`}</dd>
      </dl>
      <p className="muted small">Context for a long-term buyer, not a buy signal.</p>
    </Card>
  )
}
