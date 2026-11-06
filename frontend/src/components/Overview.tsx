import { useState } from 'react'
import { useExposure, useJobStatus, useLists } from '../api/hooks'
import type { Exposure, ListEntry } from '../api/schemas'
import { useSelection } from '../store/selection'
import { BiggestMovesCard } from './BiggestMovesCard'
import { leanCounts, localDate, needsAttention, portfolioToday } from './dashboard'
import { pct } from './format'
import { LeanPill } from './LeanPill'
import { PRICE_LABELS_SHORT } from './lean'
import { useNow } from './useNow'

const usd = (v: number) => v.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const share = (v: number) => `${(v * 100).toFixed(1)}%`

function greeting(now: Date): string {
  const h = now.getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

function Rows({ title, entries, exposure }: { title: string; entries: ListEntry[]; exposure?: Exposure }) {
  const select = useSelection((s) => s.select)
  const positions = new Map((exposure?.positions ?? []).map((p) => [p.ticker, p]))
  const showValue = positions.size > 0
  if (!entries.length) return null
  return (
    <>
      <tr className="group-row">
        <td colSpan={showValue ? 9 : 7}>{title}</td>
      </tr>
      {entries.map((e) => {
        const pos = positions.get(e.ticker)
        return (
          <tr
            key={e.ticker}
            className="click-row"
            tabIndex={0}
            onClick={() => select(e.ticker)}
            onKeyDown={(ev) => ev.key === 'Enter' && select(e.ticker)}
          >
            <td>
              <b>{e.ticker}</b>{' '}
              {e.thesis_verdict === 'challenges' && (
                <span className="reason-flag" aria-label="Your reason is being challenged" title="Your reason is being challenged">
                  ⚠
                </span>
              )}{' '}
              {e.name && <span className="muted small">{e.name}</span>}
            </td>
            <td className="num">{e.price !== null ? `$${e.price.toFixed(2)}` : '—'}</td>
            <td className={`num ${(e.day_change_pct ?? 0) >= 0 ? 'up' : 'down'}`}>{pct(e.day_change_pct)}</td>
            {showValue && <td className="num">{pos ? usd(pos.value) : ''}</td>}
            {showValue && <td className="num">{pos ? share(pos.weight) : ''}</td>}
            <td>
              <LeanPill lean={e.lean} aiStatus={e.ai_status} />
            </td>
            <td>{e.price_label ? PRICE_LABELS_SHORT[e.price_label] : '—'}</td>
            <td>{e.kind === 'etf' ? <span className="muted">ETF</span> : (e.next_earnings ?? '—')}</td>
            <td>
              {e.hype_warning ? (
                <span className="pill pill-hype">Hype warning</span>
              ) : e.hype_warning === false ? (
                <span className="up">✓</span>
              ) : (
                '—'
              )}
            </td>
          </tr>
        )
      })}
    </>
  )
}

export function Overview() {
  const { data } = useLists()
  const { data: job } = useJobStatus()
  const { data: exposure } = useExposure()
  const setView = useSelection((s) => s.setView)
  const select = useSelection((s) => s.select)
  const now = useNow()
  const [hello] = useState(() => greeting(new Date()))
  const holdings = data?.holdings ?? []
  const watching = data?.watching ?? []
  const all = [...holdings, ...watching]
  const counts = leanCounts(holdings, watching)
  const attention = needsAttention(all, localDate(now))
  const today = exposure ? portfolioToday(exposure, holdings) : null
  const nextEarnings = attention.find((i) => i.kind === 'earnings') ??
    all
      .filter((e) => e.kind !== 'etf' && e.next_earnings && e.next_earnings >= localDate(now))
      .sort((a, b) => a.next_earnings!.localeCompare(b.next_earnings!))
      .map((e) => ({ ticker: e.ticker, text: e.next_earnings! }))[0]
  const lastRun = job?.last_run
    ? new Date(job.last_run).toLocaleString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })
    : null
  const showValue = !!exposure?.positions.length

  return (
    <article className="reading overview">
      <section className="card overview-head">
        <div>
          <h1>{hello}</h1>
          <p className="muted small">{lastRun ? `Last morning refresh: ${lastRun}` : 'The morning refresh has not run yet.'}</p>
        </div>
      </section>

      <section className="tiles" role="region" aria-label="Portfolio summary">
        <div className="card tile">
          <h3 className="card-title">Portfolio value</h3>
          {today ? (
            <>
              <b className="tile-big">{usd(today.value)}</b>
              <span className={today.change >= 0 ? 'up' : 'down'}>
                {`${today.change >= 0 ? '+' : '-'}${usd(Math.abs(today.change))} (${today.changePct >= 0 ? '+' : ''}${today.changePct.toFixed(2)}%) today`}
              </span>
            </>
          ) : (
            <button type="button" className="link-button small" onClick={() => setView('exposure')}>
              Add share counts in Exposure
            </button>
          )}
        </div>
        <div className="card tile">
          <h3 className="card-title">Lean mix</h3>
          <div className="tile-leans">
            <span className="chip chip-bull">{counts.bullish} bullish</span>
            <span className="chip">{counts.neutral} neutral</span>
            <span className="chip chip-bear">{counts.bearish} bearish</span>
          </div>
        </div>
        <div className="card tile">
          <h3 className="card-title">Needs attention</h3>
          <b className="tile-big">{attention.length}</b>
          <span className="muted small">{attention.length ? 'see the list below' : 'all quiet'}</span>
        </div>
        <div className="card tile">
          <h3 className="card-title">Next earnings</h3>
          {nextEarnings ? (
            <button type="button" className="link-button tile-link" onClick={() => select(nextEarnings.ticker)}>
              <b>{nextEarnings.ticker}</b> · {nextEarnings.text}
            </button>
          ) : (
            <span className="muted">None scheduled</span>
          )}
        </div>
      </section>

      <BiggestMovesCard entries={all} />

      <div className="rail">
        <section className="card" role="region" aria-label="Needs attention">
          <h3 className="card-title">Needs attention</h3>
          {attention.length === 0 ? (
            <p className="up">Nothing needs your attention today ✓</p>
          ) : (
            <ul className="attention-list">
              {attention.map((i) => (
                <li key={`${i.ticker}-${i.kind}`}>
                  <button type="button" onClick={() => select(i.ticker)}>
                    <span className={`att-icon att-${i.kind}`} aria-hidden="true">
                      {i.kind === 'earnings' ? '📅' : '⚠'}
                    </span>
                    <b>{i.ticker}</b> <span>{i.text}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card" role="region" aria-label="Top real exposures">
          <h3 className="card-title">Top real exposures</h3>
          {exposure && exposure.underlying.length > 0 ? (
            <>
              <ul className="bars">
                {exposure.underlying.slice(0, 5).map((u) => (
                  <li key={u.symbol} title={`${u.symbol}: ${share(u.weight)}`}>
                    <span className="bar-label">
                      <b>{u.symbol}</b>
                    </span>
                    <span className="bar-track">
                      <span className="bar-fill" style={{ width: `${Math.max(u.weight * 100, 1)}%` }} />
                    </span>
                    <span className="bar-value">{share(u.weight)}</span>
                  </li>
                ))}
              </ul>
              <button type="button" className="link-button small" onClick={() => setView('exposure')}>
                See full exposure
              </button>
            </>
          ) : (
            <p className="muted small">Enter share counts in Exposure to see what you really own.</p>
          )}
        </section>
      </div>

      {data && all.length === 0 ? (
        <p className="notice">Add tickers in the sidebar to see them here.</p>
      ) : (
        <section className="card">
          <table className="overview-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th className="num">Price</th>
                <th className="num">Day</th>
                {showValue && <th className="num">Value</th>}
                {showValue && <th className="num">Weight</th>}
                <th>Lean</th>
                <th>Add more?</th>
                <th>Next earnings</th>
                <th>Hype</th>
              </tr>
            </thead>
            <tbody>
              <Rows title="My holdings" entries={holdings} exposure={exposure} />
              <Rows title="Watching" entries={watching} exposure={exposure} />
            </tbody>
          </table>
        </section>
      )}
    </article>
  )
}
