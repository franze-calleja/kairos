import type { AISummary, NewsItem } from '../../api/schemas'
import { Card } from './Card'
import { ClaimList } from './Citations'

export function DriversCard({ ai, sources }: { ai: AISummary; sources: NewsItem[] }) {
  return (
    <Card title="What's driving it">
      <ClaimList claims={ai.drivers} sources={sources} />
    </Card>
  )
}
