import { useState, type FormEvent } from 'react'
import { apiError } from '../api/client'
import { useAddTrade, useClose, usePortfolio, type NewTrade } from '../api/hooks'
import { normalizeTicker } from '../api/tickers'
import { fmtShares, nyToday } from './buys'
import { shortDay } from './moves'

type Side = 'buy' | 'sell'
type Mode = 'amount' | 'shares'

/** Cents for normal prices, 4 decimals for sub-$1 ones; drops Yahoo's float noise. */
const roundPrice = (v: number) => Number(v.toFixed(v >= 1 ? 2 : 4))

/** Log a buy or sell. The price defaults to that day's close and can be edited. */
export function AddTradeForm() {
  const [side, setSide] = useState<Side>('buy')
  const [mode, setMode] = useState<Mode>('amount')
  const [tickerText, setTickerText] = useState('')
  const [lookup, setLookup] = useState<string | null>(null)
  const [date, setDate] = useState(nyToday)
  const [qty, setQty] = useState('')
  const [typedPrice, setTypedPrice] = useState<string | null>(null) // null = use the close
  const [notice, setNotice] = useState<string | null>(null)
  const close = useClose(lookup, date)
  const { data: portfolio } = usePortfolio()
  const save = useAddTrade()

  const priceText = typedPrice ?? (close.data ? String(roundPrice(close.data.close)) : '')
  const price = Number(priceText)
  const quantity = Number(qty)
  const position = portfolio?.positions.find((p) => p.ticker === lookup)
  const preview =
    mode === 'amount' && quantity > 0 && price > 0 ? `= ${fmtShares(quantity / price)} shares` : null

  function commitTicker() {
    const t = normalizeTicker(tickerText)
    if (t !== lookup) {
      setLookup(t || null)
      setTypedPrice(null) // a new ticker gets its own close
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    const t = normalizeTicker(tickerText)
    if (t && t !== lookup) {
      // The ticker changed without leaving the field: load its own price before saving.
      commitTicker()
      setNotice(`Got the price for ${t}. Check it, then press Save.`)
      return
    }
    if (!t || !(price > 0) || !(quantity > 0)) return
    setNotice(null)
    const trade: NewTrade = { ticker: t, side, date, price, ...(mode === 'amount' ? { amount: quantity } : { shares: quantity }) }
    save.mutate(trade, { onSuccess: () => setQty('') })
  }

  return (
    <section className="card add-trade">
      <h3 className="card-title">Add a buy</h3>
      <form onSubmit={submit} className="trade-form">
        <div className="ranges" role="group" aria-label="Buy or sell">
          {(['buy', 'sell'] as const).map((s) => (
            <button key={s} type="button" aria-pressed={side === s} onClick={() => setSide(s)}>
              {s === 'buy' ? 'Buy' : 'Sell'}
            </button>
          ))}
        </div>
        <input
          aria-label="Ticker"
          placeholder="Ticker"
          value={tickerText}
          onChange={(e) => setTickerText(e.target.value)}
          onBlur={commitTicker}
          spellCheck={false}
        />
        <input
          type="date"
          aria-label="US trade date"
          value={date}
          max={nyToday()}
          onChange={(e) => setDate(e.target.value)} // a typed fill price is kept
        />
        <div className="ranges" role="group" aria-label="Amount or shares">
          <button type="button" aria-pressed={mode === 'amount'} onClick={() => setMode('amount')}>
            $ amount
          </button>
          <button type="button" aria-pressed={mode === 'shares'} onClick={() => setMode('shares')}>
            Shares
          </button>
        </div>
        <input
          type="number"
          step="any"
          min="0"
          aria-label={mode === 'amount' ? 'Amount in dollars' : 'Shares'}
          placeholder={mode === 'amount' ? '$ amount' : 'Shares'}
          value={qty}
          onChange={(e) => setQty(e.target.value)}
        />
        <input
          type="number"
          step="any"
          min="0"
          aria-label="Price per share"
          placeholder="Price"
          value={priceText}
          onChange={(e) => setTypedPrice(e.target.value)}
        />
        <button type="submit" className="primary" disabled={save.isPending}>
          Save
        </button>
      </form>
      <p className="muted small trade-notes">
        {typedPrice === null && close.data && <span>(close on {shortDay(close.data.date)}) </span>}
        {close.isError && <span className="error-text">{apiError(close.error)} </span>}
        {preview && <span>{preview} </span>}
        {side === 'sell' && position && (
          <button
            type="button"
            className="link-button"
            onClick={() => {
              setMode('shares')
              setQty(String(position.shares))
            }}
          >
            Sell all
          </button>
        )}
      </p>
      {notice && <p className="small">{notice}</p>}
      <p className="muted small">Bought after midnight your time? Use the previous day (US date).</p>
      {save.isError && <p className="error-text">{apiError(save.error)}</p>}
    </section>
  )
}
