import { useState, type FormEvent } from 'react'
import { apiError } from '../../api/client'
import { useSetThesis } from '../../api/hooks'
import type { ListName, Reading, ThesisCheck } from '../../api/schemas'
import { Card } from './Card'
import { ClaimList } from './Citations'

const MAX = 200
const UNCHECKED: Partial<Record<Reading['ai_status'], string>> = {
  not_enough_signal: 'too little recent news',
  budget_exhausted: 'AI request limit reached',
  unavailable: 'AI unavailable',
  not_configured: 'no GEMINI_API_KEY set',
}
const VERDICTS: Record<ThesisCheck['verdict'], { label: string; tone: string }> = {
  supports: { label: 'Supports ✓', tone: 'chip-bull' },
  challenges: { label: 'Challenges ⚠', tone: 'warn' },
  mixed: { label: 'Mixed', tone: '' },
  no_signal: { label: 'No clear signal', tone: '' },
}

export function ReasonCard({
  ticker,
  list,
  thesis,
  reading,
}: {
  ticker: string
  list: ListName | null
  thesis: string | null
  reading: Reading
}) {
  const [draft, setDraft] = useState(thesis ?? '')
  const save = useSetThesis()

  if (!list) {
    return (
      <Card title="Your reason">
        <p className="muted small">Add this ticker to a list to save a reason.</p>
      </Card>
    )
  }

  const check = reading.ai?.thesis_check
  const current = !!thesis && reading.thesis_checked === thesis
  const stale = !!thesis && !current

  function submit(e: FormEvent) {
    e.preventDefault()
    save.mutate({ list: list!, ticker, thesis: draft.trim() || null })
  }

  return (
    <Card title="Your reason" className={current && check?.verdict === 'challenges' ? 'card-warn' : ''}>
      <form onSubmit={submit} className="reason-form">
        <textarea
          aria-label={`Your reason for ${ticker}`}
          placeholder={`Why do you ${list === 'holdings' ? 'hold' : 'watch'} ${ticker}? e.g. "AI data-center demand"`}
          maxLength={MAX}
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <div className="reason-actions">
          <span className="muted small">
            {draft.trim().length}/{MAX}
          </span>
          <button type="submit" className="link-button small" disabled={save.isPending}>
            Save reason
          </button>
        </div>
        {save.isError && <p className="error-text">{apiError(save.error)}</p>}
      </form>
      {stale && <p className="muted small">Refresh to check your updated reason</p>}
      {current && !check && (
        <p className="muted small">
          Couldn't check your reason this time ({UNCHECKED[reading.ai_status] ?? 'no AI verdict'}). It's checked again
          at the next refresh.
        </p>
      )}
      {current && check && (
        <div className="reason-check">
          <span className={`chip ${VERDICTS[check.verdict].tone}`}>{VERDICTS[check.verdict].label}</span>
          {check.text ? (
            <ClaimList claims={[{ text: check.text, source_ids: check.source_ids }]} sources={reading.sources} />
          ) : (
            <p className="muted small">This week's news doesn't bear on it either way.</p>
          )}
        </div>
      )}
    </Card>
  )
}
