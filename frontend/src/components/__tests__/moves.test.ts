import { describe, expect, test } from 'vitest'
import type { ChangeItem, ListEntry, Move } from '../../api/schemas'
import { biggestMoves, changeText, marketLine, moveHeadline, sinceWhen } from '../moves'

const notableDrop: Move = {
  date: '2026-11-05',
  change_pct: -9.3,
  typical_pct: 2.5,
  notable: true,
  biggest_since: null,
  market_open: false,
  market_change_pct: null,
  market_notable: null,
  market_share: null,
}
const calmUp: Move = { ...notableDrop, change_pct: 0.4, notable: false }

test('sinceWhen phrasing', () => {
  expect(sinceWhen('2026-11-05', '2026-04-01')).toBe('in 7 months')
  expect(sinceWhen('2026-11-05', '2025-12-01')).toBe('in 11 months')
  expect(sinceWhen('2026-11-05', '2026-10-05')).toBe('in 1 month')
  expect(sinceWhen('2026-11-05', '2026-10-15')).toBe('in 3 weeks')
  expect(sinceWhen('2026-11-05', '2026-10-29')).toBeNull() // under 2 weeks
  expect(sinceWhen('2026-11-05', null)).toBe('in the past year')
})

describe('moveHeadline', () => {
  test('notable with a since phrase', () => {
    expect(moveHeadline({ ...notableDrop, biggest_since: '2026-04-01' }, 'NVDA')).toBe(
      'Down 9.3% on Thu Nov 5 — its biggest one-day drop in 7 months.',
    )
    expect(moveHeadline({ ...notableDrop, change_pct: 6.1 }, 'NVDA')).toBe(
      'Up 6.1% on Thu Nov 5 — its biggest one-day gain in the past year.',
    )
  })
  test('notable but a larger move happened recently', () => {
    expect(moveHeadline({ ...notableDrop, biggest_since: '2026-10-30' }, 'NVDA')).toBe(
      'Down 9.3% on Thu Nov 5 — an unusually big move for NVDA.',
    )
  })
  test('normal, unknown-typical and flat days', () => {
    expect(moveHeadline(calmUp, 'NVDA')).toBe('Up 0.4% on Thu Nov 5 — a normal day for NVDA.')
    expect(moveHeadline({ ...calmUp, typical_pct: null }, 'NVDA')).toBe('Up 0.4% on Thu Nov 5.')
    expect(moveHeadline({ ...calmUp, change_pct: 0 }, 'NVDA')).toBe('Unchanged on Thu Nov 5 — a normal day for NVDA.')
  })
})

test('marketLine bands', () => {
  const m = (share: Move['market_share'], mkt: number) => marketLine({ ...notableDrop, market_change_pct: mkt, market_share: share })
  expect(m('half', -4.4)).toBe('The S&P 500 fell 4.4% the same day, so roughly half of the drop was the whole market.')
  expect(m('market', -8.0)).toBe('The S&P 500 fell 8.0% the same day, so most of the drop was the whole market.')
  expect(m('ticker', -1.0)).toBe('The S&P 500 fell 1.0% the same day, so most of the drop was specific to this ticker.')
  expect(m('opposite', 0.6)).toBe('The S&P 500 rose 0.6% the same day, so this drop went against the market.')
  expect(marketLine({ ...calmUp, market_change_pct: 0.2, market_share: 'half' })).toBeNull()
  expect(marketLine(notableDrop)).toBeNull()
})

describe('changeText', () => {
  const since = '2026-11-05T13:00:00+00:00'
  const item = (i: Partial<ChangeItem>): ChangeItem => ({ kind: 'lean', since, ...i }) as ChangeItem
  test('lean, with and without a different comparison reading', () => {
    expect(changeText(item({ before: 'bullish', after: 'neutral' }), since)).toBe('Lean: Bullish → Neutral')
    expect(
      changeText(item({ before: 'bullish', after: 'neutral', since: '2026-11-03T13:00:00+00:00' }), since),
    ).toBe('Lean: Bullish → Neutral (vs Nov 3)')
  })
  test('other kinds', () => {
    expect(changeText(item({ kind: 'price_label', before: 'near_average', after: 'below_range' }), since)).toBe(
      'Add more?: now well below its recent range (was near its long-term average)',
    )
    expect(changeText(item({ kind: 'verdict', before: 'supports', after: 'mixed' }), since)).toBe(
      'Your reason: Supports → Mixed',
    )
    expect(changeText(item({ kind: 'hype', before: 'clear', after: 'warning' }), since)).toBe('Hype warning signs appeared')
    expect(changeText(item({ kind: 'hype', before: 'warning', after: 'clear' }), since)).toBe('Hype warning signs cleared')
    expect(changeText(item({ kind: 'target', before: '327.14', after: '310.00' }), since)).toBe(
      'Average analyst target: $327 → $310',
    )
    expect(changeText(item({ kind: 'new_articles', count: 14 }), since)).toBe('14 new articles read')
    expect(changeText(item({ kind: 'new_articles', count: 1 }), since)).toBe('1 new article read')
  })
})

test('biggestMoves keeps only latest-date notable rows, ranked by unusualness', () => {
  const e = (ticker: string, p: Partial<ListEntry>) => ({ ticker, ...p }) as ListEntry
  const a = e('A', { move_date: '2026-11-05', move_notable: true, move_change_pct: -5, move_typical_pct: 1, market_notable: true })
  const entries = [
    e('B', { move_date: '2026-11-05', move_notable: true, move_change_pct: -9, move_typical_pct: 3, market_change_pct: -4.4 }),
    a,
    e('C', { move_date: '2026-11-05', move_notable: false, move_change_pct: 0.2, move_typical_pct: 1 }),
    e('D', { move_date: '2026-10-29', move_notable: true, move_change_pct: -12, move_typical_pct: 2 }),
    e('E', { move_date: null }),
    a, // a ticker in both lists appears once
  ]
  const r = biggestMoves(entries)
  expect(r.rows.map((x) => x.ticker)).toEqual(['A', 'B'])
  expect(r.skipped).toBe(1)
  expect(r.date).toBe('2026-11-05')
  expect(r.marketChangePct).toBe(-4.4)
  expect(r.marketNotable).toBe(true)
  expect(biggestMoves([e('E', { move_date: null })]).date).toBeNull()
})

test('a short price history never claims "in the past year"', () => {
  expect(sinceWhen('2026-11-05', null, '2026-07-01')).toBe('in its 4 months of price history')
  expect(sinceWhen('2026-11-05', null, '2025-11-06')).toBe('in the past year')
  expect(moveHeadline({ ...notableDrop, history_start: '2026-08-20' }, 'NEWCO')).toBe(
    'Down 9.3% on Thu Nov 5 — its biggest one-day drop in its 2 months of price history.',
  )
})

test('cheap-stock targets keep cents', () => {
  const since = '2026-11-05T13:00:00+00:00'
  expect(changeText({ kind: 'target', before: '4.10', after: '4.40', since } as ChangeItem, since)).toBe(
    'Average analyst target: $4.10 → $4.40',
  )
})
