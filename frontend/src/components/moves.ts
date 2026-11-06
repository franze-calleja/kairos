import type { ChangeItem, ListEntry, Move } from '../api/schemas'
import { daysBetween, dollars } from './format'
import { PRICE_LABELS_LONG } from './lean'

export const MAX_BIGGEST_MOVES = 5

const LEANS: Record<string, string> = { bullish: 'Bullish', neutral: 'Neutral', bearish: 'Bearish' }
const VERDICTS: Record<string, string> = {
  supports: 'Supports',
  challenges: 'Challenges',
  mixed: 'Mixed',
  no_signal: 'No clear signal',
}

function localDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** "Thu Nov 5" from an ISO date (no timezone shift). */
export function shortDay(iso: string): string {
  const d = localDate(iso)
  const weekday = d.toLocaleDateString('en-US', { weekday: 'short' })
  const month = d.toLocaleDateString('en-US', { month: 'short' })
  return `${weekday} ${month} ${d.getDate()}`
}

/** "Nov 3" from a timestamp, in the viewer's timezone. */
function monthDay(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

const FULL_YEAR_DAYS = 330 // ~a year of trading history

function monthsBetween(fromIso: string, toIso: string): number {
  const a = localDate(fromIso)
  const b = localDate(toIso)
  return (b.getFullYear() - a.getFullYear()) * 12 + (b.getMonth() - a.getMonth()) - (b.getDate() < a.getDate() ? 1 : 0)
}

/** How long since a same-direction move this big: months, weeks (2-4), or null when recent. */
export function sinceWhen(
  moveDate: string,
  biggestSince: string | null | undefined,
  historyStart?: string | null,
): string | null {
  if (!biggestSince) {
    if (!historyStart || daysBetween(historyStart, moveDate) >= FULL_YEAR_DAYS) return 'in the past year'
    const have = monthsBetween(historyStart, moveDate)
    return `in its ${have} month${have === 1 ? '' : 's'} of price history`
  }
  const months = monthsBetween(biggestSince, moveDate)
  if (months >= 1) return `in ${months} month${months === 1 ? '' : 's'}`
  const weeks = Math.floor(daysBetween(biggestSince, moveDate) / 7)
  return weeks >= 2 ? `in ${weeks} weeks` : null
}

export function moveHeadline(move: Move, ticker: string): string {
  const day = shortDay(move.date)
  const size = Math.abs(move.change_pct).toFixed(1)
  const start =
    move.change_pct === 0 ? `Unchanged on ${day}` : `${move.change_pct < 0 ? 'Down' : 'Up'} ${size}% on ${day}`
  if (move.notable) {
    const when = sinceWhen(move.date, move.biggest_since, move.history_start)
    const what = move.change_pct < 0 ? 'drop' : 'gain'
    return when ? `${start} — its biggest one-day ${what} ${when}.` : `${start} — an unusually big move for ${ticker}.`
  }
  return move.typical_pct == null ? `${start}.` : `${start} — a normal day for ${ticker}.`
}

export function marketLine(move: Move): string | null {
  const mkt = move.market_change_pct
  if (!move.notable || mkt == null || !move.market_share) return null
  const what = move.change_pct < 0 ? 'drop' : 'gain'
  const lead = `The S&P 500 ${mkt < 0 ? 'fell' : 'rose'} ${Math.abs(mkt).toFixed(1)}% the same day, so`
  switch (move.market_share) {
    case 'market':
      return `${lead} most of the ${what} was the whole market.`
    case 'half':
      return `${lead} roughly half of the ${what} was the whole market.`
    case 'ticker':
      return `${lead} most of the ${what} was specific to this ticker.`
    case 'opposite':
      return `${lead} this ${what} went against the market.`
  }
}

function lowerFirst(s: string): string {
  return s.charAt(0).toLowerCase() + s.slice(1)
}

function priceLabel(key: string): string {
  return lowerFirst(PRICE_LABELS_LONG[key as keyof typeof PRICE_LABELS_LONG] ?? key)
}

export function changeText(item: ChangeItem, headerSince: string): string {
  const vs = item.since !== headerSince ? ` (vs ${monthDay(item.since)})` : ''
  const b = item.before ?? ''
  const a = item.after ?? ''
  switch (item.kind) {
    case 'lean':
      return `Lean: ${LEANS[b] ?? b} → ${LEANS[a] ?? a}${vs}`
    case 'verdict':
      return `Your reason: ${VERDICTS[b] ?? b} → ${VERDICTS[a] ?? a}${vs}`
    case 'price_label':
      return `Add more?: now ${priceLabel(a)} (was ${priceLabel(b)})`
    case 'hype':
      return a === 'warning' ? 'Hype warning signs appeared' : 'Hype warning signs cleared'
    case 'target':
      return `Average analyst target: ${dollars(Number(b))} → ${dollars(Number(a))}`
    case 'new_articles': {
      const n = item.count ?? 0
      return `${n} new article${n === 1 ? '' : 's'} read`
    }
  }
}

function unusualness(e: ListEntry): number {
  const change = Math.abs(e.move_change_pct ?? 0)
  return e.move_typical_pct ? change / e.move_typical_pct : change
}

export type BiggestMoves = {
  date: string | null
  marketChangePct: number | null
  marketNotable: boolean
  rows: ListEntry[]
  skipped: number
}

/** Notable movers for the latest move date; tickers with older readings are counted, not shown. */
export function biggestMoves(entries: ListEntry[]): BiggestMoves {
  const unique = [...new Map(entries.map((e) => [e.ticker, e])).values()].filter((e) => e.move_date)
  if (!unique.length) return { date: null, marketChangePct: null, marketNotable: false, rows: [], skipped: 0 }
  const date = unique
    .map((e) => e.move_date as string)
    .sort()
    .at(-1) as string
  const latest = unique.filter((e) => e.move_date === date)
  return {
    date,
    marketChangePct: latest.find((e) => e.market_change_pct != null)?.market_change_pct ?? null,
    marketNotable: latest.some((e) => e.market_notable),
    rows: latest
      .filter((e) => e.move_notable)
      .sort((x, y) => unusualness(y) - unusualness(x))
      .slice(0, MAX_BIGGEST_MOVES),
    skipped: unique.length - latest.length,
  }
}
