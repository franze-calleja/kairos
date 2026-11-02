import { expect, test } from 'vitest'
import { leanCounts, needsAttention, nextRefresh, portfolioToday } from '../dashboard'

const e = (o: Record<string, unknown>) =>
  ({
    ticker: 'X', lean: null, ai_status: null, name: null, kind: 'stock', price: null, day_change_pct: null,
    price_label: null, next_earnings: null, hype_warning: false, updated_at: null, shares: null, thesis: null,
    thesis_verdict: null, ...o,
  }) as never

const exposure = {
  total_value: 5000,
  positions: [
    { ticker: 'NVDA', shares: 10, price: 200, value: 2000, weight: 0.4, name: 'NVIDIA', kind: 'stock' as const },
    { ticker: 'QQQ', shares: 5, price: 600, value: 3000, weight: 0.6, name: 'QQQ', kind: 'etf' as const },
  ],
  underlying: [], rest_of_funds: 0, sectors: [], missing_prices: [],
}

test("today's change uses each position's day move", () => {
  const entries = [e({ ticker: 'NVDA', day_change_pct: -4 }), e({ ticker: 'QQQ', day_change_pct: 2 })]
  const t = portfolioToday(exposure, entries)!
  // NVDA: 2000 now after -4% => was 2083.33 (-83.33); QQQ: 3000 after +2% => was 2941.18 (+58.82)
  expect(t.value).toBe(5000)
  expect(t.change).toBeCloseTo(-24.51, 1)
  expect(t.changePct).toBeCloseTo((-24.51 / 5024.51) * 100, 2)
  expect(portfolioToday({ ...exposure, total_value: 0, positions: [] }, entries)).toBeNull()
})

test('lean counts count each ticker once across lists', () => {
  const holdings = [e({ ticker: 'NVDA', lean: 'bullish' }), e({ ticker: 'VOO', lean: 'neutral' })]
  const watching = [e({ ticker: 'NVDA', lean: 'bullish' }), e({ ticker: 'GOOGL', lean: 'bearish' }), e({ ticker: 'AAPL' })]
  expect(leanCounts(holdings, watching)).toEqual({ bullish: 1, neutral: 1, bearish: 1 })
})

test('needs attention lists challenged reasons, hype warnings and earnings within 7 days', () => {
  const items = needsAttention(
    [
      e({ ticker: 'NVDA', thesis_verdict: 'challenges', next_earnings: '2026-11-07' }),
      e({ ticker: 'PUMP', hype_warning: true }),
      e({ ticker: 'MSFT', next_earnings: '2026-11-20' }),
      e({ ticker: 'AAPL', next_earnings: '2026-11-03' }),
      e({ ticker: 'QQQ', kind: 'etf', next_earnings: '2026-11-04' }),
    ],
    '2026-11-03',
  )
  expect(items.map((i) => `${i.ticker}:${i.kind}`)).toEqual([
    'NVDA:reason',
    'PUMP:hype',
    'AAPL:earnings',
    'NVDA:earnings',
  ])
  expect(items.find((i) => i.ticker === 'AAPL')!.text).toBe('Earnings today')
  expect(items.find((i) => i.kind === 'earnings' && i.ticker === 'NVDA')!.text).toBe('Earnings in 4 days')
})

test('next refresh picks the next morning or evening time', () => {
  const s = { morning_refresh_time: '07:00', evening_refresh_time: '21:00' }
  expect(nextRefresh(s, new Date(2026, 10, 3, 12, 0))).toBe('Today 9:00 PM')
  expect(nextRefresh(s, new Date(2026, 10, 3, 22, 0))).toBe('Tomorrow 7:00 AM')
  expect(nextRefresh(s, new Date(2026, 10, 3, 6, 0))).toBe('Today 7:00 AM')
  expect(nextRefresh({ morning_refresh_time: '07:00', evening_refresh_time: null }, new Date(2026, 10, 3, 12, 0))).toBe(
    'Tomorrow 7:00 AM',
  )
})
