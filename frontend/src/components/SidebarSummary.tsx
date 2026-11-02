import { useExposure, useLists, useSettings } from '../api/hooks'
import { useSelection } from '../store/selection'
import { leanCounts, localDate, needsAttention, nextRefresh, portfolioToday } from './dashboard'
import { useNow } from './useNow'

const usd = (v: number) => v.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const MAX_ITEMS = 4

export function SidebarSummary() {
  const { data: lists } = useLists()
  const { data: exposure } = useExposure()
  const { data: settings } = useSettings()
  const select = useSelection((s) => s.select)
  const setView = useSelection((s) => s.setView)
  const now = useNow()
  if (!lists) return null

  const entries = [...lists.holdings, ...lists.watching]
  const today = exposure ? portfolioToday(exposure, lists.holdings) : null
  const counts = leanCounts(lists.holdings, lists.watching)
  const items = needsAttention(entries, localDate(now))

  return (
    <section className="glance" role="region" aria-label="At a glance">
      {today ? (
        <div className="glance-value">
          <b>{usd(today.value)}</b>
          <span className={today.change >= 0 ? 'up' : 'down'}>
            {`${today.change >= 0 ? '+' : '-'}${usd(Math.abs(today.change))} (${today.changePct >= 0 ? '+' : ''}${today.changePct.toFixed(2)}%) today`}
          </span>
        </div>
      ) : (
        exposure && (
          <button type="button" className="link-button small" onClick={() => setView('exposure')}>
            Add share counts to see your portfolio value
          </button>
        )
      )}
      <div className="glance-leans">
        <span>
          <i className="lean-dot dot-bullish" /> {counts.bullish} bullish
        </span>
        <span>
          <i className="lean-dot dot-neutral" /> {counts.neutral} neutral
        </span>
        <span>
          <i className="lean-dot dot-bearish" /> {counts.bearish} bearish
        </span>
      </div>
      {items.length > 0 && (
        <ul className="glance-attention">
          {items.slice(0, MAX_ITEMS).map((i) => (
            <li key={`${i.ticker}-${i.kind}`}>
              <button type="button" onClick={() => select(i.ticker)}>
                <b>{i.ticker}</b> · {i.text}
              </button>
            </li>
          ))}
          {items.length > MAX_ITEMS && <li className="muted small">+{items.length - MAX_ITEMS} more on the home page</li>}
        </ul>
      )}
      {settings && <p className="muted small glance-next">Next refresh {nextRefresh(settings, now)}</p>}
    </section>
  )
}
