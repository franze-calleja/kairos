import { useEffect, useState } from 'react'
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

function ReadingSkeleton({ ticker }: { ticker: string }) {
  return (
    <div className="reading skeleton" role="status" aria-label="Loading reading">
      <p className="muted">
        <span className="spinner" aria-hidden="true" /> Reading {ticker}… this can take ~20 seconds.
      </p>
      <div className="sk sk-title" />
      <div className="sk sk-chart" />
      <div className="sk sk-card" />
      <div className="grid">
        <div className="sk sk-card" />
        <div className="sk sk-card" />
        <div className="sk sk-card" />
      </div>
    </div>
  )
}

const UPDATED_MESSAGE_MS = 4000

export function ReadingPanel({ ticker }: { ticker: string }) {
  const { data: reading, isPending, isError, error } = useReading(ticker)
  const refresh = useRefreshReading()
  const [justUpdated, setJustUpdated] = useState(false)

  useEffect(() => {
    if (!justUpdated) return
    const t = setTimeout(() => setJustUpdated(false), UPDATED_MESSAGE_MS)
    return () => clearTimeout(t)
  }, [justUpdated])

  if (isPending) return <ReadingSkeleton ticker={ticker} />
  if (isError) return <p className="error-box">{apiError(error)}</p>

  const aiMessage = AI_MESSAGES[reading.ai_status]
  const showAI = reading.ai_status === 'ok' && reading.ai
  return (
    <article className={`reading ${refresh.isPending ? 'is-refreshing' : ''}`} aria-busy={refresh.isPending}>
      <LeanHeader
        reading={reading}
        onRefresh={() => refresh.mutate(reading.ticker, { onSuccess: () => setJustUpdated(true) })}
        refreshing={refresh.isPending}
      />
      {refresh.isPending && (
        <p className="notice notice-busy" role="status">
          <span className="spinner" aria-hidden="true" /> Refreshing {reading.ticker}… this can take ~20 seconds.
        </p>
      )}
      {justUpdated && !refresh.isPending && (
        <p className="notice notice-ok" role="status">
          {reading.ticker} updated ✓
        </p>
      )}
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
