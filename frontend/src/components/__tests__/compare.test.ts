import { expect, test } from 'vitest'
import { oneYearReturn, rebase, topHoldingsOverlap } from '../compare'

const h = (closes: number[]) => closes.map((close, i) => ({ date: `2026-01-${String(i + 1).padStart(2, '0')}`, close }))

test('one-year return from first to last close, in percent', () => {
  const year = Array.from({ length: 252 }, (_, i) => ({ date: `d${String(i).padStart(3, '0')}`, close: i === 251 ? 110 : 100 }))
  expect(oneYearReturn(year)).toBeCloseTo(10)
  expect(oneYearReturn([])).toBeNull()
})

test('rebase starts at 100 from the given date', () => {
  const out = rebase(h([50, 55, 60]), '2026-01-02')
  expect(out).toEqual([
    { time: '2026-01-02', value: 100 },
    { time: '2026-01-03', value: (60 / 55) * 100 },
  ])
})

test('top-holdings overlap sums the smaller weight of shared names', () => {
  const a = [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.1 }, { symbol: 'MSFT', name: 'Microsoft', weight: 0.08 }]
  const b = [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.2 }, { symbol: 'AVGO', name: 'Broadcom', weight: 0.05 }]
  expect(topHoldingsOverlap(a, b)).toEqual({ overlap: 0.1, shared: ['NVDA'] })
})

test('no one-year return for less than about a year of history', () => {
  expect(oneYearReturn(h(Array.from({ length: 60 }, (_, i) => 100 + i)))).toBeNull()
  const year = Array.from({ length: 250 }, (_, i) => ({ date: `d${String(i).padStart(3, '0')}`, close: 100 + i }))
  expect(oneYearReturn(year)).toBeCloseTo(249)
})
