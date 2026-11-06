import type { Reading } from '../../api/schemas'
import { daysBetween } from '../format'
import { changeText, marketLine, moveHeadline } from '../moves'
import { Card } from './Card'
import { ClaimList } from './Citations'

const EARNINGS_SOON_DAYS = 14

function localIsoDate(timestamp: string): string {
  const d = new Date(timestamp)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function earningsLine(reading: Reading): string | null {
  const next = reading.events.next_earnings
  if (!next) return null
  const days = daysBetween(localIsoDate(reading.created_at), next)
  if (days < 0 || days > EARNINGS_SOON_DAYS) return null
  return days === 0 ? 'Earnings today' : `Earnings in ${days} day${days === 1 ? '' : 's'}`
}

function ReasonLine({ reading }: { reading: Reading }) {
  if (reading.ai_status !== 'ok' || !reading.ai) return <p className="muted">AI read not available for this reading.</p>
  const reason = reading.ai.move_reason
  if (!reason) return <p className="muted">No company-specific news found for this move.</p>
  return <ClaimList claims={[reason]} sources={reading.sources} />
}

/** The last trading day's move in context, plus what changed since the previous reading. */
export function WhyItMovedCard({ reading }: { reading: Reading }) {
  const move = reading.move
  if (!move) return null
  const market = marketLine(move)
  const changes = reading.changes
  const earnings = earningsLine(reading)
  const lines = [...(changes?.items.map((i) => changeText(i, changes.since)) ?? []), ...(earnings ? [earnings] : [])]
  const since = changes
    ? new Date(changes.since).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
    : null

  return (
    <Card title="Why it moved" className="why-moved">
      <p className={move.notable ? 'move-headline notable' : 'move-headline'}>{moveHeadline(move, reading.ticker)}</p>
      {move.market_open && <p className="muted small">US market is open; this covers the last completed day.</p>}
      {market && <p>{market}</p>}
      {move.notable && <ReasonLine reading={reading} />}
      {lines.length > 0 && (
        <div className="since-last">
          <h4 className="card-subtitle">{since ? `Since the last reading (${since})` : 'Coming up'}</h4>
          <ul className="changes">
            {lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  )
}
