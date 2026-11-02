import type { NewsItem } from '../../api/schemas'
import { Card } from './Card'

export function SourcesList({ sources }: { sources: NewsItem[] }) {
  return (
    <Card title="Sources">
      <p className="muted small">{sources.length} articles and filings read for this reading.</p>
      <ol className="sources">
        {sources.map((s) => (
          <li key={s.id}>
            <a href={s.url} target="_blank" rel="noopener noreferrer">
              {s.title}
            </a>{' '}
            <span className="muted small">
              {s.source} · {s.published_at.slice(0, 10)}
              {s.related_ticker !== 'MARKET' ? ` · ${s.related_ticker}` : ' · market'}
            </span>
          </li>
        ))}
      </ol>
    </Card>
  )
}
