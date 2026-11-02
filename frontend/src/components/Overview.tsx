import { useState } from 'react'
import { useJobStatus, useLists } from '../api/hooks'
import type { ListEntry } from '../api/schemas'
import { useSelection } from '../store/selection'
import { pct } from './format'
import { LeanPill } from './LeanPill'
import { PRICE_LABELS_SHORT } from './lean'

function greeting(now: Date): string {
  const h = now.getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

function Rows({ title, entries }: { title: string; entries: ListEntry[] }) {
  const select = useSelection((s) => s.select)
  if (!entries.length) return null
  return (
    <>
      <tr className="group-row">
        <td colSpan={7}>{title}</td>
      </tr>
      {entries.map((e) => (
        <tr
          key={e.ticker}
          className="click-row"
          tabIndex={0}
          onClick={() => select(e.ticker)}
          onKeyDown={(ev) => ev.key === 'Enter' && select(e.ticker)}
        >
          <td>
            <b>{e.ticker}</b> {e.name && <span className="muted small">{e.name}</span>}
          </td>
          <td className="num">{e.price !== null ? `$${e.price.toFixed(2)}` : '—'}</td>
          <td className={`num ${(e.day_change_pct ?? 0) >= 0 ? 'up' : 'down'}`}>{pct(e.day_change_pct)}</td>
          <td>
            <LeanPill lean={e.lean} aiStatus={e.ai_status} />
          </td>
          <td>{e.price_label ? PRICE_LABELS_SHORT[e.price_label] : '—'}</td>
          <td>{e.kind === 'etf' ? <span className="muted">ETF</span> : (e.next_earnings ?? '—')}</td>
          <td>{e.hype_warning ? <span className="pill pill-hype">Hype warning</span> : e.hype_warning === false ? <span className="up">✓</span> : '—'}</td>
        </tr>
      ))}
    </>
  )
}

export function Overview() {
  const { data } = useLists()
  const { data: job } = useJobStatus()
  const [hello] = useState(() => greeting(new Date()))
  const all = [...(data?.holdings ?? []), ...(data?.watching ?? [])]
  const count = (lean: string) => all.filter((e) => e.lean === lean).length
  const lastRun = job?.last_run
    ? new Date(job.last_run).toLocaleString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })
    : null

  return (
    <article className="reading overview">
      <section className="card overview-head">
        <div>
          <h1>{hello}</h1>
          <p className="muted small">{lastRun ? `Last morning refresh: ${lastRun}` : 'The morning refresh has not run yet.'}</p>
        </div>
        <div className="chips">
          <span className="chip chip-bull">{count('bullish')} bullish</span>
          <span className="chip">{count('neutral')} neutral</span>
          <span className="chip chip-bear">{count('bearish')} bearish</span>
        </div>
      </section>
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
                <th>Lean</th>
                <th>Add more?</th>
                <th>Next earnings</th>
                <th>Hype</th>
              </tr>
            </thead>
            <tbody>
              <Rows title="My holdings" entries={data?.holdings ?? []} />
              <Rows title="Watching" entries={data?.watching ?? []} />
            </tbody>
          </table>
        </section>
      )}
    </article>
  )
}
