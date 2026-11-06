import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { Move, Reading } from '../../api/schemas'
import { reading } from '../../test/fixtures/reading'
import { WhyItMovedCard } from '../reading/WhyItMovedCard'

const drop: Move = {
  date: '2026-10-30',
  change_pct: -9.3,
  typical_pct: 2.5,
  notable: true,
  biggest_since: '2026-04-01',
  market_open: false,
  market_change_pct: -4.4,
  market_notable: true,
  market_share: 'half',
}

const base: Reading = { ...reading, events: { ...reading.events, next_earnings: null } }
const withMove = (move: Move, extra: Partial<Reading> = {}): Reading => ({ ...base, move, ...extra })
const reason = { text: 'Data-center spending fears hit chip stocks', source_ids: ['abc'] }

test('notable move: headline, market line, cited reason', () => {
  render(<WhyItMovedCard reading={withMove(drop, { ai: { ...reading.ai!, move_reason: reason } })} />)
  expect(screen.getByText('Why it moved')).toBeInTheDocument()
  expect(screen.getByText('Down 9.3% on Fri Oct 30 — its biggest one-day drop in 6 months.')).toBeInTheDocument()
  expect(
    screen.getByText('The S&P 500 fell 4.4% the same day, so roughly half of the drop was the whole market.'),
  ).toBeInTheDocument()
  expect(screen.getByText(/Data-center spending fears hit chip stocks/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '[1]' })).toHaveAttribute('href', 'https://example.com/guidance')
})

test('notable move without a reason says no company news was found', () => {
  render(<WhyItMovedCard reading={withMove(drop, { ai: { ...reading.ai!, move_reason: null } })} />)
  expect(screen.getByText('No company-specific news found for this move.')).toBeInTheDocument()
})

test('notable move without an AI read says so instead', () => {
  render(<WhyItMovedCard reading={withMove(drop, { ai: null, ai_status: 'budget_exhausted' })} />)
  expect(screen.getByText('AI read not available for this reading.')).toBeInTheDocument()
  expect(screen.queryByText(/No company-specific news/)).not.toBeInTheDocument()
})

test('normal day shows only the headline', () => {
  render(<WhyItMovedCard reading={withMove({ ...drop, change_pct: 0.4, notable: false })} />)
  expect(screen.getByText('Up 0.4% on Fri Oct 30 — a normal day for NVDA.')).toBeInTheDocument()
  expect(screen.queryByText(/S&P 500/)).not.toBeInTheDocument()
  expect(screen.queryByText(/No company-specific news/)).not.toBeInTheDocument()
})

test('market open note', () => {
  render(<WhyItMovedCard reading={withMove({ ...drop, notable: false, market_open: true })} />)
  expect(screen.getByText('US market is open; this covers the last completed day.')).toBeInTheDocument()
})

test('since the last reading lists changes and the earnings countdown', () => {
  const since = '2026-11-01T13:00:00Z'
  const r = withMove(
    { ...drop, notable: false },
    {
      events: { ...reading.events, next_earnings: '2026-11-07' },
      changes: { since, items: [{ kind: 'lean', before: 'bullish', after: 'neutral', since }] },
    },
  )
  render(<WhyItMovedCard reading={r} />)
  expect(screen.getByText(/Since the last reading/)).toBeInTheDocument()
  expect(screen.getByText('Lean: Bullish → Neutral')).toBeInTheDocument()
  expect(screen.getByText('Earnings in 5 days')).toBeInTheDocument()
})

test('no changes and no near earnings hides the section', () => {
  const since = '2026-11-01T13:00:00Z'
  render(<WhyItMovedCard reading={withMove(drop, { changes: { since, items: [] } })} />)
  expect(screen.queryByText(/Since the last reading/)).not.toBeInTheDocument()
})

test('readings saved before this feature render nothing', () => {
  const { container } = render(<WhyItMovedCard reading={base} />)
  expect(container).toBeEmptyDOMElement()
})
