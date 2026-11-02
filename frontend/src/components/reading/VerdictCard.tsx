import type { Reading } from '../../api/schemas'
import { useSelection } from '../../store/selection'
import { daysBetween, pct } from '../format'
import { PRICE_LABELS_SHORT } from '../lean'

const AI_MESSAGES: Partial<Record<Reading['ai_status'], string>> = {
  not_enough_signal: 'Not enough signal: too little recent coverage to form a view.',
  budget_exhausted: 'Daily AI limit reached. Numbers below are still current.',
  unavailable: 'AI summary unavailable right now.',
  not_configured: 'Add GEMINI_API_KEY to .env to enable AI summaries.',
}
const LEAN_LABELS = { bullish: 'Bullish', neutral: 'Neutral', bearish: 'Bearish' } as const

function eventChip(reading: Reading): string | null {
  const e = reading.events
  if (e.next_earnings) {
    const days = daysBetween(reading.created_at, e.next_earnings)
    return e.earnings_within_7d ? `Earnings in ${days} days` : `Earnings ${e.next_earnings}`
  }
  const macro = e.macro[0]
  return macro ? `${macro.kind === 'FOMC' ? 'Fed decision' : 'CPI'} ${macro.date}` : null
}

export function VerdictCard({
  reading,
  onRefresh,
  refreshing,
}: {
  reading: Reading
  onRefresh: () => void
  refreshing: boolean
}) {
  const showTrackRecord = useSelection((s) => s.showTrackRecord)
  const ok = reading.ai_status === 'ok' && reading.ai
  const lean = ok ? reading.ai!.lean : null
  const hype = reading.hype.some((f) => f.triggered)
  const event = eventChip(reading)
  const updated = new Date(reading.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  // Older readings have no takeaway; show nothing rather than repeating a driver.
  const takeaway = ok ? reading.ai!.takeaway?.text : AI_MESSAGES[reading.ai_status]

  return (
    <section className={`card verdict verdict-${lean ?? 'none'}`} role="region" aria-label="Verdict">
      <div className="verdict-lean">
        <div className="verdict-big">{lean ? LEAN_LABELS[lean] : 'No AI read'}</div>
        {ok && <div className="muted small">{reading.ai!.confidence} confidence</div>}
      </div>
      <div className="verdict-body">
        <h1>
          {reading.ticker} <span className="muted name">{reading.name}</span>
          {reading.kind === 'etf' && <span className="kind-tag">ETF</span>}
        </h1>
        {reading.price && (
          <p className="price-line">
            ${reading.price.last_price.toFixed(2)}{' '}
            <span className={(reading.price.day_change_pct ?? 0) >= 0 ? 'up' : 'down'}>
              {pct(reading.price.day_change_pct)}
            </span>
          </p>
        )}
        {takeaway && <p className={ok ? 'takeaway' : 'takeaway muted'}>{takeaway}</p>}
      </div>
      <div className="verdict-side">
        <div className="chips">
          {reading.price && <span className="chip">{PRICE_LABELS_SHORT[reading.price.label]}</span>}
          {event && <span className="chip">{event}</span>}
          {hype ? <span className="chip warn">Hype warning</span> : <span className="chip">No hype flags</span>}
        </div>
        <p className="muted small">
          updated {updated}{' '}
          <button type="button" className="link-button" onClick={onRefresh} disabled={refreshing}>
            {refreshing ? 'refreshing…' : 'refresh'}
          </button>{' '}
          ·{' '}
          <button
            type="button"
            className="link-button"
            aria-label={`Track record for ${reading.ticker}`}
            onClick={() => showTrackRecord(reading.ticker)}
          >
            track record
          </button>
        </p>
      </div>
    </section>
  )
}
