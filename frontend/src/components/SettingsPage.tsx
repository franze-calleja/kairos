import { apiError } from '../api/client'
import { useBackupNow, useRunMorningJob, useSettings } from '../api/hooks'

const mark = (ok: boolean) => (ok ? '✓' : '✗')

export function SettingsPage() {
  const { data, isPending, isError, error } = useSettings()
  const run = useRunMorningJob()
  const backup = useBackupNow()
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
        <p className="small">
          {data.evening_refresh_time
            ? `Evening refresh at ${data.evening_refresh_time}: readings only, before the US open.`
            : 'Evening refresh: off.'}
        </p>
        <p className="muted small">Last run: {data.last_morning_run ?? 'never'}</p>
        <button type="button" className="primary" onClick={() => run.mutate()} disabled={run.isPending}>
          Run morning refresh now
        </button>
        {run.isSuccess && <p className="small">Morning refresh started. It can take several minutes.</p>}
        {run.isError && <p className="error-text">{apiError(run.error)}</p>}
      </section>
      <section className="card">
        <h3 className="card-title">Backups</h3>
        {data.backup_dir ? (
          <>
            <p className="small">
              Once a day to the <code>backups</code> folder next to Kairos; keeps the last {data.backup_keep}.
            </p>
            <p className="muted small">
              Last backup: {data.last_backup ? new Date(data.last_backup).toLocaleString() : 'not yet'}
            </p>
            <button type="button" className="primary" onClick={() => backup.mutate()} disabled={backup.isPending}>
              Back up now
            </button>
            {backup.isSuccess && <p className="small">Saved {backup.data.file}</p>}
            {backup.isError && <p className="error-text">{apiError(backup.error)}</p>}
          </>
        ) : (
          <p className="muted small">Backups are off (BACKUP_DIR is empty).</p>
        )}
      </section>
    </article>
  )
}
