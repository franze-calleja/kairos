import type { Reading } from '../../api/schemas'
import { analystPosition } from './analyst'
import { Card } from './Card'

const dollars = (v: number) => `$${Math.round(v)}`

function fromToday(target: number, price: number): string {
  const p = Math.round((target / price - 1) * 100)
  const sign = p > 0 ? '+' : p < 0 ? '−' : ''
  return `${sign}${Math.abs(p)}% from today`
}

function Box({ label, value, price, highlight = false }: { label: string; value: number; price: number | null; highlight?: boolean }) {
  return (
    <div className={highlight ? 'target-box mid' : 'target-box'}>
      <div className="target-box-label">{label}</div>
      <div className="target-box-value">{dollars(value)}</div>
      {price ? <div className={value >= price ? 'up small' : 'down small'}>{fromToday(value, price)}</div> : null}
    </div>
  )
}

/** Wall Street analysts' 12-month targets: other people's opinion, labelled as such. */
export function AnalystTargetsCard({
  quick,
  price,
  ticker,
}: {
  quick: Reading['quick']
  price: number | null
  ticker?: string
}) {
  const { target_mean: mean, target_low: low, target_high: high, analyst_count: count } = quick
  if (mean == null || !count) return null
  const range = low != null && high != null && high >= low

  return (
    <Card title="What analysts expect (12 months)" className="analyst-targets">
      <p>
        On average, <b>{count} analysts</b> think {ticker ?? 'the stock'} will be around <b>{dollars(mean)}</b> in a
        year.{price ? <> Today it's <b>${price.toFixed(2)}</b>.</> : null}
      </p>
      <div className={range ? 'target-boxes' : 'target-boxes single'}>
        {range && <Box label="Lowest" value={low} price={price} />}
        <Box label="Average" value={mean} price={price} highlight />
        {range && <Box label="Highest" value={high} price={price} />}
      </div>
      {range && price ? <p>{analystPosition(price, low, high)}</p> : null}
      <p className="muted small">
        {quick.analyst_rating ? `Average rating: ${quick.analyst_rating} · ` : ''}These are analysts' opinions, not a
        Kairos forecast. Analysts are often too optimistic.
      </p>
    </Card>
  )
}
