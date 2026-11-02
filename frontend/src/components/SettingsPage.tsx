import { apiError } from '../api/client'
import { useRunMorningJob, useSettings } from '../api/hooks'

const mark = (ok: boolean) => (ok ? '✓' : '✗')

export function SettingsPage() {
  const { data, isPending, isError, error } = useSettings()
  const run = useRunMorningJob()
  if (isPending) return <p className="muted">Loading settings…</p>
  if (isError) return <p className="error-box">{apiError(error)}</p>
  const usage = Math.min(100, (data.budget.day / Math.max(data.budget.rpd, 1)) * 100)
  return (
    <article className="reading settings">
      <h1>Settings</h1>
      <p className="muted">Change these in your .env file and restart Kairos.</p>
      <section className="card">
        <h3 className="card-title">Data sources</h3>
        <ul className="plain">
          <li>Gemini {mark(data.gemini_configured)}</li>
          <li>Finnhub {mark(data.finnhub_configured)}</li>
          <li>SEC filings {mark(data.sec_configured)}</li>
          <li>Reddit {data.reddit_enabled ? 'on' : 'off'}</li>
        </ul>
        <p className="muted small">Model: {data.gemini_model}</p>
      </section>
      <section className="card">
        <h3 className="card-title">AI budget</h3>
        <div className="meter">
          <div className="meter-fill" style={{ width: `${usage}%` }} />
        </div>
        <p className="small">
          {data.budget.day} / {data.budget.rpd} AI requests today
        </p>
      </section>
      <section className="card">
        <h3 className="card-title">Morning refresh</h3>
        <p>
          Every day at {data.morning_refresh_time} ({data.tz}). Readings are reused for {data.reading_cache_hours} hours.
        </p>
        <p className="muted small">Last run: {data.last_morning_run ?? 'never'}</p>
        <button type="button" className="primary" onClick={() => run.mutate()} disabled={run.isPending}>
          Run morning refresh now
        </button>
        {run.isSuccess && <p className="small">Morning refresh started. It can take several minutes.</p>}
        {run.isError && <p className="error-text">{apiError(run.error)}</p>}
      </section>
    </article>
  )
}
