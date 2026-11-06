import type { Reading } from '../../api/schemas'
import { pct } from '../format'
import { Card } from './Card'

const usd = (v: number) => `$${v.toFixed(2)}`

/** Wall Street analysts' 12-month targets: other people's opinion, labelled as such. */
export function AnalystTargetsCard({ quick, price }: { quick: Reading['quick']; price: number | null }) {
  const { target_mean: mean, target_low: low, target_high: high, analyst_count: count } = quick
  if (mean == null || !count) return null
  const upside = price ? (mean / price - 1) * 100 : null
  const span = low != null && high != null && high > low ? high - low : null
  const at = (v: number) => `${Math.min(100, Math.max(0, ((v - low!) / span!) * 100))}%`

  return (
    <Card title="Analyst targets (12 months)">
      <p className="target-line">
        <b className="tile-big">{usd(mean)}</b>{' '}
        {upside !== null && <span className={upside >= 0 ? 'up' : 'down'}>{pct(upside)} vs today</span>}
      </p>
      <p className="muted small">
        Average of {count} analysts{quick.target_median != null ? ` · median ${usd(quick.target_median)}` : ''}
        {quick.analyst_rating ? ` · Average rating: ${quick.analyst_rating}` : ''}
      </p>
      {span !== null && (
        <div className="target-range" title={`Low ${usd(low!)} · average ${usd(mean)} · high ${usd(high!)}`}>
          <div className="target-track">
            <span className="target-mean" style={{ left: at(mean) }} aria-hidden="true" />
            {price !== null && <span className="target-now" style={{ left: at(price) }} aria-hidden="true" />}
          </div>
          <div className="target-ends muted small">
            <span>{`${usd(low!)} – ${usd(high!)}`}</span>
            <span>
              <i className="key-now" /> today <i className="key-mean" /> average
            </span>
          </div>
        </div>
      )}
      <p className="muted small">These are analysts' opinions, not a Kairos forecast.</p>
    </Card>
  )
}
