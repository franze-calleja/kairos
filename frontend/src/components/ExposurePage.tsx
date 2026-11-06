import { useState, type FormEvent } from 'react'
import { apiError } from '../api/client'
import { useExposure, useLists, useSetShares } from '../api/hooks'
import type { ListEntry } from '../api/schemas'
import { useSelection } from '../store/selection'
import { fmtShares } from './buys'

const pct = (v: number) => `${(v * 100).toFixed(1)}%`
const usd = (v: number) => v.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

function SharesInput({ entry }: { entry: ListEntry }) {
  const [value, setValue] = useState(entry.shares?.toString() ?? '')
  const [invalid, setInvalid] = useState(false)
  const [sent, setSent] = useState<number | null>(entry.shares)
  const save = useSetShares()

  function commit(e?: FormEvent) {
    e?.preventDefault()
    const trimmed = value.trim()
    const shares = trimmed === '' ? null : Number(trimmed)
    if (shares !== null && (!Number.isFinite(shares) || shares < 0)) {
      setInvalid(true) // e.g. "12,5" or "Infinity": never send, never clear the saved count
      return
    }
    setInvalid(false)
    if (shares === sent) return // Enter then blur shouldn't save twice
    setSent(shares)
    save.mutate({ ticker: entry.ticker, shares })
  }

  return (
    <form onSubmit={commit} className="shares-form">
      <input
        aria-label={`Shares of ${entry.ticker}`}
        inputMode="decimal"
        placeholder="0"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => commit()}
      />
      {invalid && <span className="error-text">Enter a number like 12.5</span>}
      {save.isError && <span className="error-text">{apiError(save.error)}</span>}
    </form>
  )
}

export function ExposurePage() {
  const { data: lists } = useLists()
  const { data, isPending, isError, error } = useExposure()
  const holdings = lists?.holdings ?? []

  return (
    <article className="reading exposure">
      <section className="card">
        <h1>Exposure</h1>
        <p className="muted small">
          What you really own once your ETFs are looked through. Share counts stay on this machine and are never
          sent to the AI.
        </p>
      </section>

      <div className="rail">
        <div className="rail-main">
          {isPending && <p className="muted">Calculating…</p>}
          {isError && <p className="error-box">{apiError(error)}</p>}
          {data && data.total_value === 0 && (
            <p className="notice">Enter how many shares you own to see your real exposure.</p>
          )}
          {data && data.total_value > 0 && (
            <section className="card">
              <h3 className="card-title">What you really own</h3>
              <table className="overview-table" aria-label="What you really own">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th className="num">Weight</th>
                    <th>Where it comes from</th>
                  </tr>
                </thead>
                <tbody>
                  {data.underlying.map((u) => (
                    <tr key={u.symbol}>
                      <td>
                        <b>{u.symbol}</b> <span className="muted small">{u.name}</span>
                      </td>
                      <td className="num">{pct(u.weight)}</td>
                      <td className="chips">
                        {u.direct > 0 && <span className="chip">direct {pct(u.direct)}</span>}
                        {Object.entries(u.via).map(([etf, w]) => (
                          <span key={etf} className="chip">
                            via {etf} {pct(w)}
                          </span>
                        ))}
                      </td>
                    </tr>
                  ))}
                  {data.rest_of_funds > 0 && (
                    <tr className="rest-row">
                      <td>Rest of funds (beyond top 10 holdings)</td>
                      <td className="num">{pct(data.rest_of_funds)}</td>
                      <td className="muted small">Yahoo lists only each fund's top 10 holdings</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>
          )}
        </div>

        <div className="rail-side">
          <section className="card">
            <h3 className="card-title">Your positions</h3>
            {holdings.length === 0 && <p className="muted small">Add holdings in the sidebar first.</p>}
            <table className="positions">
              <tbody>
                {holdings.map((h) => {
                  const pos = data?.positions.find((p) => p.ticker === h.ticker)
                  return (
                    <tr key={h.ticker}>
                      <td>
                        <b>{h.ticker}</b>
                      </td>
                      <td>
                        {h.shares_source === 'trades' ? (
                          <button
                            type="button"
                            className="link-button"
                            onClick={() => useSelection.getState().setView('buys')}
                          >
                            {fmtShares(h.shares ?? 0)} · from My buys
                          </button>
                        ) : (
                          <SharesInput key={`${h.ticker}-${h.shares ?? ''}`} entry={h} />
                        )}
                      </td>
                      <td className="num muted small">{pos ? usd(pos.value) : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {data && data.total_value > 0 && (
              <p className="total-line">
                Total <b>{usd(data.total_value)}</b>
              </p>
            )}
            {data && data.missing_prices.length > 0 && (
              <p className="muted small">
                No price for {data.missing_prices.join(', ')} yet; left out of the totals. Open its reading to fetch one.
              </p>
            )}
          </section>

          {data && data.sectors.length > 0 && (
            <section className="card">
              <h3 className="card-title">By sector</h3>
              <ul className="bars">
                {data.sectors.map((s) => (
                  <li key={s.sector} title={`${s.sector}: ${pct(s.weight)}`}>
                    <span className="bar-label">{s.sector}</span>
                    <span className="bar-track">
                      <span className="bar-fill" style={{ width: `${Math.max(s.weight * 100, 1)}%` }} />
                    </span>
                    <span className="bar-value">{pct(s.weight)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </article>
  )
}
