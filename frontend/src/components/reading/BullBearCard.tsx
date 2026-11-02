import type { AISummary, NewsItem } from '../../api/schemas'
import { Card } from './Card'
import { ClaimList } from './Citations'

export function BullBearCard({ ai, sources }: { ai: AISummary; sources: NewsItem[] }) {
  return (
    <div className="two-col">
      <Card title="Bull case" className="card-bull">
        <ClaimList claims={ai.bull_case} sources={sources} />
      </Card>
      <Card title="Bear case" className="card-bear">
        <ClaimList claims={ai.bear_case} sources={sources} />
      </Card>
    </div>
  )
}
