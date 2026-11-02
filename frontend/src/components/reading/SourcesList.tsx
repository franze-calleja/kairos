import { useState } from 'react'
import type { NewsItem } from '../../api/schemas'
import { Card } from './Card'

const TOP = 5
const FEEDS: Record<string, string> = {
  finnhub: 'Finnhub',
  google_news: 'Google News',
  sec: 'SEC EDGAR',
  reddit: 'Reddit',
}

export function SourcesList({ sources }: { sources: NewsItem[] }) {
  const [all, setAll] = useState(false)
  const shown = all ? sources : sources.slice(0, TOP)
  return (
    <Card title="Sources">
      <p className="muted small">{sources.length} articles and filings read for this reading.</p>
      <ol className="sources">
        {shown.map((s) => (
          <li key={s.id}>
            <a href={s.url} target="_blank" rel="noopener noreferrer">
              {s.title}
            </a>{' '}
            <span className="muted small">
              {s.outlet ?? FEEDS[s.source] ?? s.source} · {s.published_at.slice(0, 10)}
              {s.related_ticker === 'MARKET' ? ' · market' : ''}
            </span>
          </li>
        ))}
      </ol>
      {sources.length > TOP && (
        <button type="button" className="link-button small" onClick={() => setAll(!all)}>
          {all ? 'Show fewer' : `Show all ${sources.length}`}
        </button>
      )}
    </Card>
  )
}
