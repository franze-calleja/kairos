import { createChart, LineSeries } from 'lightweight-charts'
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { apiError } from '../api/client'
import { useLists, useReading } from '../api/hooks'
import type { ListEntry, Reading } from '../api/schemas'
import { normalizeTicker } from '../api/tickers'
import { useSelection } from '../store/selection'
import { oneYearReturn, rebase, topHoldingsOverlap } from './compare'
import { money, num, pct, ratioPct } from './format'
import { PRICE_LABELS_SHORT } from './lean'

const COLORS = ['#4f46e5', '#d97706'] as const // validated pair (light surface)
const RANGES = { '1M': 21, '6M': 126, '1Y': Infinity } as const
type Range = keyof typeof RANGES
const LEANS = { bullish: 'Bullish', neutral: 'Neutral', bearish: 'Bearish' } as const

type Cell = { text: ReactNode; better?: boolean }
type Row = { label: string; a: Cell; b: Cell }

/** Mark the lower value as better only where lower is unambiguously better. */
function lowerBetter(label: string, a: number | null | undefined, b: number | null | undefined, fmt: (v: number) => string): Row {
  const has = (v: number | null | undefined): v is number => v !== null && v !== undefined
  return {
    label,
    a: { text: has(a) ? fmt(a) : '—', better: has(a) && has(b) && a < b },
    b: { text: has(b) ? fmt(b) : '—', better: has(a) && has(b) && b < a },
  }
}

function plain(label: string, f: (r: Reading) => ReactNode, a: Reading, b: Reading): Row {
  return { label, a: { text: f(a) ?? '—' }, b: { text: f(b) ?? '—' } }
}

const VERDICTS = { supports: 'Supports ✓', challenges: 'Challenges ⚠', mixed: 'Mixed', no_signal: 'No clear signal' } as const

function rows(a: Reading, b: Reading, reasons: Record<string, ListEntry | undefined>): Row[] {
  const stock = (r: Reading, v: number | null) => (r.kind === 'stock' && v !== null ? v : null)
  const etf = (r: Reading, v: number | null) => (r.kind === 'etf' && v !== null ? v : null)
  const out: Row[] = [
    plain('Price', (r) => (r.price ? `$${r.price.last_price.toFixed(2)} (${pct(r.price.day_change_pct)})` : null), a, b),
    plain('Lean', (r) => (r.ai_status === 'ok' && r.ai ? `${LEANS[r.ai.lean]} · ${r.ai.confidence}` : 'No AI read'), a, b),
    plain('Takeaway', (r) => r.ai?.takeaway?.text ?? null, a, b),
    plain('Add more?', (r) => (r.price ? PRICE_LABELS_SHORT[r.price.label] : null), a, b),
    plain('vs 200-day avg', (r) => pct(r.price?.pct_vs_ma200), a, b),
    plain('From 52-week high', (r) => pct(r.price?.pct_from_52w_high), a, b),
    lowerBetter('30-day volatility', a.price?.volatility_30d, b.price?.volatility_30d, (v) => `${v.toFixed(0)}% / yr`),
    plain('1-year return', (r) => pct(oneYearReturn(r.price?.history ?? [])), a, b),
  ]
  const anyStock = a.kind === 'stock' || b.kind === 'stock'
  const anyEtf = a.kind === 'etf' || b.kind === 'etf'
  if (anyStock) {
    out.push(
      plain('Market cap', (r) => (stock(r, r.quick.market_cap) !== null ? money(r.quick.market_cap) : '—'), a, b),
      plain('P/E (trailing)', (r) => {
        if (stock(r, r.quick.trailing_pe) === null) return '—'
        return r.quick.sector_pe !== null ? `${num(r.quick.trailing_pe)} (sector ${num(r.quick.sector_pe)})` : num(r.quick.trailing_pe)
      }, a, b),
      plain('Revenue growth', (r) => (stock(r, r.quick.revenue_growth) !== null ? ratioPct(r.quick.revenue_growth, 0) : '—'), a, b),
      plain('Analyst target (avg)', (r) => {
        const mean = r.quick.target_mean
        if (r.kind !== 'stock' || mean == null) return '—'
        const now = r.price?.last_price
        return now ? `$${mean.toFixed(2)} (${pct((mean / now - 1) * 100)})` : `$${mean.toFixed(2)}`
      }, a, b),
    )
  }
  if (anyEtf) {
    out.push(
      lowerBetter('Expense ratio', etf(a, a.quick.expense_ratio), etf(b, b.quick.expense_ratio), (v) => ratioPct(v, 2)),
      plain('Fund size', (r) => (etf(r, r.quick.aum) !== null ? money(r.quick.aum) : '—'), a, b),
    )
  }
  out.push(
    plain('Next earnings', (r) => (r.kind === 'etf' ? '—' : (r.events.next_earnings ?? '—')), a, b),
    plain('Hype check', (r) => (r.hype.some((f) => f.triggered) ? 'Warning' : 'No warning signs'), a, b),
  )
  if (reasons[a.ticker]?.thesis || reasons[b.ticker]?.thesis) {
    out.push(
      plain('Your reason', (r) => {
        const e = reasons[r.ticker]
        if (!e?.thesis) return '—'
        return e.thesis_verdict ? VERDICTS[e.thesis_verdict] : 'Not checked yet'
      }, a, b),
    )
  }
  return out
}

function RelativeChart({ a, b }: { a: Reading; b: Reading }) {
  const ref = useRef<HTMLDivElement>(null)
  const [range, setRange] = useState<Range>('1Y')
  useEffect(() => {
    const ha = a.price?.history ?? []
    const hb = b.price?.history ?? []
    if (!ref.current || !ha.length || !hb.length) return
    const n = Math.min(RANGES[range], ha.length, hb.length)
    const from = [ha[ha.length - n].date, hb[hb.length - n].date].sort()[1] // shared start
    const chart = createChart(ref.current, {
      height: 240,
      autoSize: true,
      layout: { textColor: '#6b7280', attributionLogo: true },
      grid: { vertLines: { visible: false }, horzLines: { color: '#f3f4f6' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    })
    chart.addSeries(LineSeries, { color: COLORS[0], lineWidth: 2, title: a.ticker }).setData(rebase(ha, from))
    chart.addSeries(LineSeries, { color: COLORS[1], lineWidth: 2, title: b.ticker }).setData(rebase(hb, from))
    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [a, b, range])
  return (
    <section className="chart-wrap">
      <div className="chart-top">
        <p className="muted small legend">
          <span className="dot" style={{ background: COLORS[0] }} /> {a.ticker}{' '}
          <span className="dot" style={{ background: COLORS[1] }} /> {b.ticker}{' '}
          <span>· both start at 100</span>
        </p>
        <div className="ranges" role="group" aria-label="Chart period">
          {(Object.keys(RANGES) as Range[]).map((r) => (
            <button key={r} type="button" aria-pressed={range === r} onClick={() => setRange(r)}>
              {r}
            </button>
          ))}
        </div>
      </div>
      <div ref={ref} className="chart" />
    </section>
  )
}

function TickerInput({ index }: { index: 0 | 1 }) {
  const compare = useSelection((s) => s.compare)
  const [value, setValue] = useState(compare[index] ?? '')
  function submit(e: FormEvent) {
    e.preventDefault()
    const t = value.trim() ? normalizeTicker(value) : null
    const next: [string | null, string | null] = [...compare]
    next[index] = t
    useSelection.setState({ compare: next })
  }
  return (
    <form onSubmit={submit}>
      <input
        aria-label={index === 0 ? 'First ticker' : 'Second ticker'}
        placeholder={index === 0 ? 'e.g. QQQ' : 'e.g. SMH'}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={submit}
        spellCheck={false}
      />
    </form>
  )
}

export function ComparePage() {
  const [ta, tb] = useSelection((s) => s.compare)
  const same = !!ta && ta === tb
  const ra = useReading(same ? null : ta)
  const rb = useReading(same ? null : tb)
  const a = ra.data
  const b = rb.data
  const { data: lists } = useLists()
  const reasons: Record<string, ListEntry | undefined> = {}
  for (const e of [...(lists?.watching ?? []), ...(lists?.holdings ?? [])]) reasons[e.ticker] = e
  const overlap =
    a?.kind === 'etf' && b?.kind === 'etf' ? topHoldingsOverlap(a.quick.top_holdings, b.quick.top_holdings) : null

  return (
    <article className="reading compare">
      <section className="card compare-head">
        <h1>Compare</h1>
        <div className="compare-inputs">
          <TickerInput index={0} />
          <span className="muted">vs</span>
          <TickerInput index={1} />
        </div>
      </section>
      {same && <p className="notice">Pick two different tickers.</p>}
      {!ta && !tb && <p className="notice">Enter two tickers to compare them side by side.</p>}
      {!!ta !== !!tb && <p className="notice">Enter a second ticker to compare.</p>}
      {[ra, rb].map((q, i) =>
        q.isError ? (
          <p key={i} className="error-box">
            {apiError(q.error)}
          </p>
        ) : null,
      )}
      {(ra.isFetching || rb.isFetching) && !(a && b) && (
        <p className="muted">
          <span className="spinner" aria-hidden="true" /> Loading readings… new tickers can take ~20 seconds each.
        </p>
      )}
      {a && b && !same && (
        <>
          <RelativeChart a={a} b={b} />
          <section className="card">
            <table className="overview-table compare-table">
              <thead>
                <tr>
                  <th />
                  <th>
                    <span className="dot" style={{ background: COLORS[0] }} /> {a.ticker}
                  </th>
                  <th>
                    <span className="dot" style={{ background: COLORS[1] }} /> {b.ticker}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows(a, b, reasons).map((r) => (
                  <tr key={r.label}>
                    <th scope="row">{r.label}</th>
                    <td>
                      <span className={r.a.better ? 'better' : undefined}>{r.a.text}</span>
                    </td>
                    <td>
                      <span className={r.b.better ? 'better' : undefined}>{r.b.text}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          {overlap && (
            <section className="card">
              <h3 className="card-title">Holdings overlap</h3>
              <p>
                <b>{(overlap.overlap * 100).toFixed(1)}% of top-10 holdings overlap</b>
              </p>
              <p className="muted small">
                {overlap.shared.length ? `Shared: ${overlap.shared.join(', ')}.` : 'No shared names among the top 10.'} Yahoo
                lists only each fund's top 10 holdings.
              </p>
            </section>
          )}
        </>
      )}
    </article>
  )
}
