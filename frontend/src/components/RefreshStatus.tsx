import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useJobStatus } from '../api/hooks'
import type { JobStatus } from '../api/schemas'

function describe(s: JobStatus): string {
  if (s.phase === 'readings') {
    const n = Math.min(s.done + 1, s.total)
    return s.current ? `Refreshing ${n} of ${s.total}: ${s.current}…` : 'Refreshing your tickers…'
  }
  if (s.phase === 'outcomes') return 'Updating track record…'
  if (s.phase === 'discover') {
    return s.total ? `Scanning S&P 500 for Discover… ${s.done} / ${s.total}` : 'Finding Discover suggestions…'
  }
  return 'Starting refresh…'
}

const DONE_MESSAGE_MS = 6000

export function RefreshStatus({ pollMs }: { pollMs?: number }) {
  const { data } = useJobStatus(pollMs ? { active: pollMs, idle: pollMs } : undefined)
  const qc = useQueryClient()
  const wasRunning = useRef(false)
  const [finishedAt, setFinishedAt] = useState<Date | null>(null)

  useEffect(() => {
    if (!data) return
    if (wasRunning.current && !data.running) {
      // Run finished: reload everything it may have changed, without a page reload.
      qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'job-status' })
      setFinishedAt(new Date())
    }
    wasRunning.current = data.running
  }, [data, qc])

  useEffect(() => {
    if (!finishedAt) return
    const t = setTimeout(() => setFinishedAt(null), DONE_MESSAGE_MS)
    return () => clearTimeout(t)
  }, [finishedAt])

  if (data?.running) {
    const pct = data.total ? Math.round((data.done / data.total) * 100) : null
    return (
      <div className="job-status" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <span>{describe(data)}</span>
        {pct !== null && (
          <span className="job-bar" aria-hidden="true">
            <span style={{ width: `${pct}%` }} />
          </span>
        )}
      </div>
    )
  }
  if (finishedAt) {
    const time = finishedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    return (
      <div className="job-status job-done" role="status" aria-live="polite">
        Updated ✓ {time}
      </div>
    )
  }
  return null
}
