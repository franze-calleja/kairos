import type { Reading } from '../../api/schemas'
import { money, num, ratioPct } from '../format'
import { Card } from './Card'

export function QuickNumbersCard({ quick }: { quick: Reading['quick'] }) {
  if (quick.kind === 'etf') {
    return (
      <Card title="Quick numbers">
        <dl className="stats">
          <dt>Expense ratio</dt>
          <dd>{ratioPct(quick.expense_ratio, 2)}</dd>
          <dt>Fund size</dt>
          <dd>{money(quick.aum)}</dd>
        </dl>
        {quick.top_holdings.length > 0 && (
          <>
            <p className="muted small">Top holdings</p>
            <ul className="holdings">
              {quick.top_holdings.map((h) => (
                <li key={h.symbol}>
                  <b>{h.symbol}</b> <span className="muted">{ratioPct(h.weight)}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
    )
  }
  return (
    <Card title="Quick numbers">
      <dl className="stats">
        <dt>Market cap</dt>
        <dd>{money(quick.market_cap)}</dd>
        <dt>P/E (trailing / forward)</dt>
        <dd>
          {num(quick.trailing_pe)} / {num(quick.forward_pe)}
        </dd>
        <dt>Sector P/E{quick.sector ? ` (${quick.sector})` : ''}</dt>
        <dd>{num(quick.sector_pe)}</dd>
        <dt>Revenue growth</dt>
        <dd>{ratioPct(quick.revenue_growth, 0)}</dd>
        <dt>Profit margin</dt>
        <dd>{ratioPct(quick.profit_margin, 0)}</dd>
      </dl>
    </Card>
  )
}
