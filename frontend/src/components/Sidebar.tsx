import { useState, type FormEvent } from 'react'
import { apiError } from '../api/client'
import { useAddTicker, useDiscover, useJobStatus, useLists, useRemoveTicker } from '../api/hooks'
import type { ListEntry, ListName } from '../api/schemas'
import { useSelection } from '../store/selection'
import { pct } from './format'
import { leanLabel } from './lean'

function LeanDot({ entry }: { entry: ListEntry }) {
  const label = leanLabel(entry.lean, entry.ai_status, !!entry.hype_warning)
  const tone = entry.hype_warning
    ? 'hype'
    : entry.ai_status === 'not_enough_signal'
      ? 'muted'
      : (entry.lean ?? 'none')
  return (
    <span className={`lean-dot dot-${tone}`} title={label}>
      <span className="sr-only">{label}</span>
    </span>
  )
}

function ListSection({ title, list, entries }: { title: string; list: ListName; entries: ListEntry[] }) {
  const [value, setValue] = useState('')
  const add = useAddTicker()
  const remove = useRemoveTicker()
  const selected = useSelection((s) => s.selected)
  const select = useSelection((s) => s.select)

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!value.trim()) return
    add.mutate({ list, ticker: value.trim() }, { onSuccess: () => setValue('') })
  }

  return (
    <section className="side-section">
      <h2 className="side-title">{title}</h2>
      {entries.map((entry) => (
        <div key={entry.ticker} className={`side-row ${selected === entry.ticker ? 'is-selected' : ''}`}>
          <button type="button" className="side-ticker" onClick={() => select(entry.ticker)}>
            <b>{entry.ticker}</b>
            {entry.day_change_pct !== null && (
              <span className={`side-change ${entry.day_change_pct >= 0 ? 'up' : 'down'}`}>
                {pct(entry.day_change_pct)}
              </span>
            )}
            <LeanDot entry={entry} />
          </button>
          <button
            type="button"
            className="side-remove"
            aria-label={`Remove ${entry.ticker} from ${title}`}
            onClick={() => remove.mutate({ list, ticker: entry.ticker })}
          >
            ×
          </button>
        </div>
      ))}
      <form onSubmit={submit} className="side-add">
        <input
          aria-label={`Add to ${title}`}
          placeholder="+ add ticker"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          spellCheck={false}
        />
      </form>
      {add.isError && <p className="error-text">{apiError(add.error)}</p>}
    </section>
  )
}

function DiscoverSection() {
  const { data } = useDiscover()
  const { data: job } = useJobStatus()
  const select = useSelection((s) => s.select)
  const scanning = job?.running && job.phase === 'discover'
  return (
    <section className="side-section">
      <h2 className="side-title">Discover ✦</h2>
      {scanning && (
        <p className="side-note">
          <span className="spinner" aria-hidden="true" />{' '}
          {job.total ? `Scanning S&P 500… ${job.done} / ${job.total}` : 'Finding suggestions…'}
        </p>
      )}
      {!scanning && !data?.items.length && <p className="side-note">Suggestions appear after the morning refresh.</p>}
      {data?.items.map((item) => (
        <button key={item.ticker} type="button" className="side-discover" onClick={() => select(item.ticker)}>
          <b>{item.ticker}</b>
          <span className="muted small">{item.reason}</span>
        </button>
      ))}
    </section>
  )
}

export function Sidebar() {
  const { data, isError, error } = useLists()
  return (
    <aside className="sidebar">
      {isError && <p className="error-text">{apiError(error)}</p>}
      <ListSection title="My Holdings" list="holdings" entries={data?.holdings ?? []} />
      <ListSection title="Watching" list="watching" entries={data?.watching ?? []} />
      <DiscoverSection />
    </aside>
  )
}
