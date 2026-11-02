import { apiError } from '../api/client'
import { useReading, useRefreshReading } from '../api/hooks'
import type { Reading } from '../api/schemas'
import { AddMoreCard } from './reading/AddMoreCard'
import { BullBearCard } from './reading/BullBearCard'
import { DataHealth } from './reading/DataHealth'
import { DriversCard } from './reading/DriversCard'
import { EventsCard } from './reading/EventsCard'
import { HypeFlagsCard } from './reading/HypeFlagsCard'
import { LeanHeader } from './reading/LeanHeader'
import { PriceChart } from './reading/PriceChart'
import { QuickNumbersCard } from './reading/QuickNumbersCard'
import { SourcesList } from './reading/SourcesList'

const AI_MESSAGES: Partial<Record<Reading['ai_status'], string>> = {
  not_enough_signal: 'Not enough signal: too little recent coverage to form a view.',
  budget_exhausted: 'Daily AI limit reached. Numbers below are still current.',
  unavailable: 'AI summary unavailable right now.',
  not_configured: 'Add GEMINI_API_KEY to .env to enable AI summaries.',
}

export function ReadingPanel({ ticker }: { ticker: string }) {
  const { data: reading, isPending, isError, error } = useReading(ticker)
  const refresh = useRefreshReading()

  if (isPending) return <p className="muted loading">Reading {ticker}… this can take ~20 seconds.</p>
  if (isError) return <p className="error-box">{apiError(error)}</p>

  const aiMessage = AI_MESSAGES[reading.ai_status]
  const showAI = reading.ai_status === 'ok' && reading.ai
  return (
    <article className="reading">
      <LeanHeader reading={reading} onRefresh={() => refresh.mutate(reading.ticker)} refreshing={refresh.isPending} />
      {refresh.isError && <p className="error-box">{apiError(refresh.error)}</p>}
      {reading.price && <PriceChart history={reading.price.history} />}
      {aiMessage && <p className="notice">{aiMessage}</p>}
      {showAI && (
        <>
          <DriversCard ai={reading.ai!} sources={reading.sources} />
          <BullBearCard ai={reading.ai!} sources={reading.sources} />
        </>
      )}
      <div className="grid">
        {reading.price && <AddMoreCard price={reading.price} />}
        <EventsCard events={reading.events} asOf={reading.created_at} />
        <HypeFlagsCard hype={reading.hype} />
        <QuickNumbersCard quick={reading.quick} />
      </div>
      <SourcesList sources={reading.sources} />
      <DataHealth health={reading.data_health} />
    </article>
  )
}
