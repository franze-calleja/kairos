import type { Exposure, ListEntry } from '../api/schemas'
import { daysBetween } from './format'

export type AttentionItem = { ticker: string; kind: 'reason' | 'hype' | 'earnings'; text: string; days?: number }

/** Portfolio value and today's move, from current values and each position's day change. */
export function portfolioToday(
  exposure: Exposure,
  entries: ListEntry[],
): { value: number; change: number; changePct: number } | null {
  if (!exposure.total_value) return null
  const dayPct = new Map(entries.map((e) => [e.ticker, e.day_change_pct ?? 0]))
  const change = exposure.positions.reduce((sum, p) => {
    const d = dayPct.get(p.ticker) ?? 0
    return sum + (p.value * d) / (100 + d) // value now minus value at yesterday's close
  }, 0)
  const before = exposure.total_value - change
  return { value: exposure.total_value, change, changePct: before ? (change / before) * 100 : 0 }
}

export function leanCounts(...lists: ListEntry[][]): { bullish: number; neutral: number; bearish: number } {
  const seen = new Map<string, ListEntry>()
  for (const e of lists.flat()) if (!seen.has(e.ticker)) seen.set(e.ticker, e)
  const counts = { bullish: 0, neutral: 0, bearish: 0 }
  for (const e of seen.values()) if (e.lean) counts[e.lean] += 1
  return counts
}

const EARNINGS_WINDOW_DAYS = 7

/** Things worth a look today: challenged reasons, hype warnings, earnings within a week. */
export function needsAttention(entries: ListEntry[], today: string): AttentionItem[] {
  const unique = [...new Map(entries.map((e) => [e.ticker, e])).values()]
  const reasons = unique
    .filter((e) => e.thesis_verdict === 'challenges')
    .map((e): AttentionItem => ({ ticker: e.ticker, kind: 'reason', text: 'Your reason is being challenged' }))
  const hype = unique
    .filter((e) => e.hype_warning)
    .map((e): AttentionItem => ({ ticker: e.ticker, kind: 'hype', text: 'Hype warning signs' }))
  const earnings = unique
    .filter((e) => e.kind !== 'etf' && e.next_earnings)
    .map((e) => ({ e, days: daysBetween(today, e.next_earnings!) }))
    .filter(({ days }) => days >= 0 && days <= EARNINGS_WINDOW_DAYS)
    .sort((a, b) => a.days - b.days)
    .map(
      ({ e, days }): AttentionItem => ({
        ticker: e.ticker,
        kind: 'earnings',
        text: days === 0 ? 'Earnings today' : `Earnings in ${days} day${days === 1 ? '' : 's'}`,
        days,
      }),
    )
  return [...reasons, ...hype, ...earnings]
}

function at(base: Date, hhmm: string, addDays = 0): Date {
  const [h, m] = hhmm.split(':').map(Number)
  const d = new Date(base)
  d.setDate(d.getDate() + addDays)
  d.setHours(h, m, 0, 0)
  return d
}

/** "Today 9:00 PM" / "Tomorrow 7:00 AM" — the next scheduled refresh in local time. */
export function nextRefresh(
  s: { morning_refresh_time: string; evening_refresh_time: string | null },
  now: Date,
): string {
  const times = [s.morning_refresh_time, s.evening_refresh_time].filter((t): t is string => !!t)
  const today = times.map((t) => at(now, t)).filter((d) => d > now)
  const next = today.length ? today.sort((a, b) => +a - +b)[0] : at(now, s.morning_refresh_time, 1)
  const time = next.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  return `${next.getDate() === now.getDate() ? 'Today' : 'Tomorrow'} ${time}`
}

export function localDate(now: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`
}
