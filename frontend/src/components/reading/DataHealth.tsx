import type { Reading } from '../../api/schemas'
import { Card } from './Card'

const NAMES = {
  yfinance: 'Yahoo prices',
  finnhub: 'Finnhub',
  google_news: 'Google News',
  sec: 'SEC filings',
  reddit: 'Reddit',
  gemini: 'Gemini AI',
} as const

export function DataHealth({ health }: { health: Reading['data_health'] }) {
  return (
    <Card title="Data health">
      <div className="chips">
        {health.map((s) => (
          <span key={s.name} className={`chip chip-${s.status}`} title={s.detail ?? s.status}>
            {NAMES[s.name]}: {s.status.replace('_', ' ')}
          </span>
        ))}
      </div>
    </Card>
  )
}
