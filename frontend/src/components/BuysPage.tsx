import { useState } from 'react'
import { apiError } from '../api/client'
import { useDeleteTrade, usePortfolio } from '../api/hooks'
import type { HistoryRow, Portfolio, Position } from '../api/schemas'
import { AddTradeForm } from './AddTradeForm'
import { fmtShares, signedUsd } from './buys'
import { pct } from './format'
import { PRICE_LABELS_SHORT } from './lean'
import { LeanPill } from './LeanPill'

export const OWN_ALREADY_HELP =
  'Already own some? Log it as one buy at your average price (Gotrade shows it on the position).'

const usd = (v: number | null | undefined) => (v == null ? '—' : `$${v.toFixed(2)}`)
const gainText = (gain: number | null, gainPct: number | null) =>
  gain == null ? '—' : `${signedUsd(gain)} (${pct(gainPct)})`
const tone = (v: number | null | undefined) => (v == null ? undefined : v >= 0 ? 'up' : 'down')

function shortDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function PositionsTable({ positions, totals, realized }: { positions: Position[]; totals: Portfolio['totals']; realized: number }) {
  return (
    <section className="card">
      <h3 className="card-title">Your positions</h3>
      <table className="overview-table buys-table" aria-label="Your positions">
        <thead>
          <tr>
            <th>Ticker</th>
            <th className="num">Shares</th>
            <th className="num">Avg cost</th>
            <th className="num">Invested</th>
            <th className="num">Value now</th>
            <th className="num">Gain</th>
            <th className="num">Your return</th>
            <th className="num">Same $ in VOO</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => (
            <tr key={p.ticker}>
              <td>
                <b>{p.ticker}</b>
              </td>
              <td className="num">{fmtShares(p.shares)}</td>
              <td className="num">{usd(p.avg_cost)}</td>
              <td className="num">{usd(p.invested)}</td>
              <td className="num">{usd(p.value)}</td>
              <td className={`num ${tone(p.gain) ?? ''}`}>{gainText(p.gain, p.gain_pct)}</td>
              <td className={`num ${tone(p.return_pct) ?? ''}`}>{pct(p.return_pct)}</td>
              <td className="num">{pct(p.voo_pct)}</td>
            </tr>
          ))}
          <tr className="total-row">
            <td>
              <b>Total</b>
            </td>
            <td />
            <td />
            <td className="num">{usd(totals.invested)}</td>
            <td className="num">{usd(totals.value)}</td>
            <td className={`num ${tone(totals.gain) ?? ''}`}>
              {gainText(totals.gain, totals.gain != null && totals.invested ? (totals.gain / totals.invested) * 100 : null)}
            </td>
            <td className={`num ${tone(totals.return_pct) ?? ''}`}>{pct(totals.return_pct)}</td>
            <td className="num">{pct(totals.voo_pct)}</td>
          </tr>
        </tbody>
      </table>
      {realized !== 0 && <p className="muted small">Realized from sales: {signedUsd(realized)}</p>}
      <p className="muted small">
        "Same $ in VOO" is what the same buys and sells would have made in the S&amp;P 500 on the same days. Prices
        only: no dividends or fees.
      </p>
    </section>
  )
}

function DeleteCell({ id }: { id: number }) {
  const [asking, setAsking] = useState(false)
  const del = useDeleteTrade()
  if (!asking)
    return (
      <button type="button" className="link-button" onClick={() => setAsking(true)}>
        Delete
      </button>
    )
  return (
    <span>
      Delete?{' '}
      <button type="button" className="link-button" onClick={() => del.mutate(id)} disabled={del.isPending}>
        Yes
      </button>{' '}
      <button type="button" className="link-button" onClick={() => setAsking(false)}>
        No
      </button>
      {del.isError && <span className="error-text"> {apiError(del.error)}</span>}
    </span>
  )
}

function sinceText(h: HistoryRow): string {
  if (h.side === 'sell' || h.since_pct == null) return '—'
  if (h.ticker === 'VOO' || h.voo_since_pct == null) return pct(h.since_pct)
  return `${pct(h.since_pct)} (VOO ${pct(h.voo_since_pct)})`
}

function HistoryTable({ history }: { history: HistoryRow[] }) {
  return (
    <section className="card">
      <h3 className="card-title">Buy history</h3>
      <table className="overview-table buys-table" aria-label="Buy history">
        <thead>
          <tr>
            <th>Date</th>
            <th>Ticker</th>
            <th />
            <th className="num">Amount</th>
            <th className="num">Price</th>
            <th>What Kairos said that day</th>
            <th className="num">Since</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {history.map((h) => (
            <tr key={h.id}>
              <td>{shortDate(h.trade_date)}</td>
              <td>
                <b>{h.ticker}</b>
              </td>
              <td className="muted">{h.side === 'buy' ? 'Buy' : 'Sell'}</td>
              <td className="num">{usd(h.amount)}</td>
              <td className="num">{usd(h.price)}</td>
              <td>
                {h.kairos_said ? (
                  <>
                    {h.kairos_said.price_label && (
                      <span className="pill">{PRICE_LABELS_SHORT[h.kairos_said.price_label]}</span>
                    )}{' '}
                    {(h.kairos_said.lean || h.kairos_said.ai_status === 'not_enough_signal') && (
                      <LeanPill lean={h.kairos_said.lean} aiStatus={h.kairos_said.ai_status} />
                    )}
                  </>
                ) : (
                  <span className="muted small">no reading that day</span>
                )}
              </td>
              <td className={`num ${tone(h.side === 'buy' ? h.since_pct : null) ?? ''}`}>{sinceText(h)}</td>
              <td>
                <DeleteCell id={h.id} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

/** The owner's logged buys and sells: positions, returns vs VOO, and history. Local only. */
export function BuysPage() {
  const { data, isError, error } = usePortfolio()
  const empty = data && data.history.length === 0
  return (
    <article className="reading buys">
      <section className="card">
        <h1>My buys</h1>
        <p className="muted small">Stays on your machine; never sent to the AI.</p>
      </section>
      {isError && <p className="error-box">{apiError(error)}</p>}
      <AddTradeForm />
      {empty && (
        <section className="card">
          <p>Log your buys to see your average cost, gains and how they compare with simply buying VOO.</p>
          <p className="muted small">{OWN_ALREADY_HELP}</p>
        </section>
      )}
      {data && !empty && (
        <>
          <PositionsTable positions={data.positions} totals={data.totals} realized={data.realized} />
          <HistoryTable history={data.history} />
        </>
      )}
    </article>
  )
}
