import type { AIStatus, Lean } from '../api/schemas'

const LABELS: Record<Lean, string> = { bullish: 'Bullish', neutral: 'Neutral', bearish: 'Bearish' }

export function leanLabel(lean: Lean | null, aiStatus: AIStatus | null, hype = false): string {
  if (hype) return 'Hype warning'
  if (aiStatus === 'not_enough_signal') return 'Not enough signal'
  return lean ? LABELS[lean] : '—'
}
