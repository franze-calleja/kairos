import { apiError } from '../api/client'
import { useTrackRecord } from '../api/hooks'
import { pct } from './format'

const LEANS = ['bullish', 'neutral', 'bearish'] as const
const HORIZONS = ['1', '5', '20'] as const

export function TrackRecordPanel({ ticker }: { ticker?: string }) {
  const { data, isPending, isError, error } = useTrackRecord(ticker)
  if (isPending) return <p className="muted">Loading track record…</p>
  if (isError) return <p className="error-box">{apiError(error)}</p>
  return (
    <article className="reading">
      <h1>Track record{ticker ? ` — ${ticker}` : ''}</h1>
      <p className="muted">
        How each lean turned out 1, 5 and 20 trading days later, compared with VOO over the same days. Only the
        first reading per ticker per day counts.
      </p>
      {data.small_sample && <p className="notice">Small sample — don't read much into this yet</p>}
      <table className="track">
        <thead>
          <tr>
            <th>Lean</th>
            <th>Days later</th>
            <th>Readings</th>
            <th>Avg change</th>
            <th>vs VOO</th>
            <th>% that rose</th>
          </tr>
        </thead>
        <tbody>
          {LEANS.flatMap((lean) =>
            HORIZONS.map((h) => {
              const s = data.by_lean[lean]?.[h]
              return (
                <tr key={`${lean}-${h}`}>
                  <td>{h === '1' ? lean : ''}</td>
                  <td>+{h}</td>
                  <td>{s?.n ?? 0}</td>
                  <td>{pct(s?.avg_change_pct)}</td>
                  <td>{pct(s?.avg_excess_pct)}</td>
                  <td>{s?.pct_positive === null || s?.pct_positive === undefined ? '—' : `${s.pct_positive.toFixed(0)}%`}</td>
                </tr>
              )
            }),
          )}
        </tbody>
      </table>
    </article>
  )
}
