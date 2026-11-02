import type { AIStatus, Lean } from '../api/schemas'

const LABELS: Record<Lean, string> = { bullish: 'Bullish', neutral: 'Neutral', bearish: 'Bearish' }

export function leanLabel(lean: Lean | null, aiStatus: AIStatus | null, hype = false): string {
  if (hype) return 'Hype warning'
  if (aiStatus === 'not_enough_signal') return 'Not enough signal'
  return lean ? LABELS[lean] : 'No reading yet'
}

export const PRICE_LABELS_SHORT = {
  stretched: 'Stretched above avg',
  near_average: 'Near long-term avg',
  below_range: 'Well below range',
  insufficient_history: 'Not enough history',
} as const
