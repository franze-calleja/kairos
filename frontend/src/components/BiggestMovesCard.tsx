import type { ListEntry } from '../api/schemas'
import { useSelection } from '../store/selection'
import { pct } from './format'
import { biggestMoves, shortDay } from './moves'

const SAME_AS_MARKET = 0.8

function rowReason(e: ListEntry): string {
  if (e.move_reason) return e.move_reason
  if (e.ai_status !== 'ok') return 'AI read not available'
  const change = e.move_change_pct ?? 0
  const market = e.market_change_pct
  const sameAsMarket =
    market != null && market !== 0 && Math.sign(market) === Math.sign(change) && Math.abs(market) >= Math.abs(change) * SAME_AS_MARKET
  return sameAsMarket ? 'About the same as the market; no company-specific news found' : 'No company-specific news found'
}

/** Holdings and watchlist tickers that moved more than usual on the last trading day. */
export function BiggestMovesCard({ entries }: { entries: ListEntry[] }) {
  const select = useSelection((s) => s.select)
  const moves = biggestMoves(entries)
  if (!moves.date) return null
  const day = shortDay(moves.date)
  const mkt = moves.marketChangePct
  const header =
    mkt != null
      ? `S&P 500 ${mkt < 0 ? 'down' : 'up'} ${Math.abs(mkt).toFixed(1)}% on ${day}${moves.marketNotable ? ' — a big day for the whole market' : ''}`
      : `Last trading day: ${day}`

  return (
    <section className="card biggest-moves" role="region" aria-label="Biggest moves">
      <h3 className="card-title">Biggest moves</h3>
      <p className="muted small">{header}</p>
      {moves.rows.length === 0 ? (
        <p className="muted">No unusual moves on the last trading day.</p>
      ) : (
        <ul className="move-rows">
          {moves.rows.map((e) => (
            <li key={e.ticker}>
              <button type="button" className="move-row" onClick={() => select(e.ticker)}>
                <b>{e.ticker}</b>
                <span className={(e.move_change_pct ?? 0) < 0 ? 'down' : 'up'}>{pct(e.move_change_pct)}</span>
                <span>{rowReason(e)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {moves.skipped > 0 && (
        <p className="muted small">
          {moves.skipped} ticker{moves.skipped === 1 ? '' : 's'} not refreshed for this day
        </p>
      )}
    </section>
  )
}
