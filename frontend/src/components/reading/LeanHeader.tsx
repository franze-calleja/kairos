import type { Reading } from '../../api/schemas'
import { LeanPill } from '../LeanPill'
import { pct } from '../format'

export function LeanHeader({ reading, onRefresh, refreshing }: { reading: Reading; onRefresh: () => void; refreshing: boolean }) {
  const hype = reading.hype.some((f) => f.triggered)
  const updated = new Date(reading.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return (
    <div className="lean-header">
      <div>
        <h1>
          {reading.ticker} <span className="muted name">{reading.name}</span>
        </h1>
        {reading.price && (
          <p className="price-line">
            ${reading.price.last_price.toFixed(2)}{' '}
            <span className={(reading.price.day_change_pct ?? 0) >= 0 ? 'up' : 'down'}>{pct(reading.price.day_change_pct)}</span>
          </p>
        )}
      </div>
      <div className="lean-right">
        <div className="pills">
          {hype && <LeanPill lean={null} aiStatus={null} hype />}
          <LeanPill lean={reading.ai?.lean ?? null} aiStatus={reading.ai_status} />
          {reading.ai && reading.ai_status === 'ok' && <span className="muted small">{reading.ai.confidence} confidence</span>}
        </div>
        <p className="muted small">
          updated {updated}{' '}
          <button type="button" className="link-button" onClick={onRefresh} disabled={refreshing}>
            {refreshing ? 'refreshing…' : 'refresh'}
          </button>
        </p>
      </div>
    </div>
  )
}
