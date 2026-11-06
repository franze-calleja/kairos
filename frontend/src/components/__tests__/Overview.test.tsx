import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'
import { useSelection } from '../../store/selection'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { Overview } from '../Overview'

const row = (o: Record<string, unknown>) => ({
  name: null, kind: 'stock', price: null, day_change_pct: null, price_label: null,
  next_earnings: null, hype_warning: false, updated_at: '2026-11-02T23:04:00Z', lean: null, ai_status: 'ok', ...o,
})

test('overview lists every ticker with its summary and opens a reading on click', async () => {
  server.use(
    http.get('/api/lists', () =>
      HttpResponse.json({
        holdings: [row({ ticker: 'NVDA', name: 'NVIDIA Corporation', lean: 'bullish', price: 204.64, day_change_pct: -4.2, price_label: 'near_average', next_earnings: '2026-11-17' })],
        watching: [row({ ticker: 'GOOGL', lean: 'bearish', price: 279.84, day_change_pct: -1.4, price_label: 'below_range' })],
      }),
    ),
  )
  renderWithClient(<Overview />)
  const nvda = await screen.findByRole('row', { name: /NVDA/ })
  expect(within(nvda).getByText('$204.64')).toBeInTheDocument()
  expect(within(nvda).getByText('-4.2%')).toBeInTheDocument()
  expect(within(nvda).getByText('Bullish')).toBeInTheDocument()
  expect(within(nvda).getByText('Near long-term avg')).toBeInTheDocument()
  expect(within(nvda).getByText('2026-11-17')).toBeInTheDocument()
  expect(screen.getByText('1 bullish')).toBeInTheDocument()
  expect(screen.getByText('1 bearish')).toBeInTheDocument()
  await userEvent.click(nvda)
  expect(useSelection.getState().selected).toBe('NVDA')
})

test('overview explains what to do when lists are empty', async () => {
  renderWithClient(<Overview />)
  expect(await screen.findByText(/Add tickers in the sidebar/)).toBeInTheDocument()
})


test('overview flags tickers whose reason is challenged', async () => {
  server.use(
    http.get('/api/lists', () =>
      HttpResponse.json({
        holdings: [row({ ticker: 'NVDA', lean: 'bullish', thesis: 'AI demand', thesis_verdict: 'challenges' })],
        watching: [],
      }),
    ),
  )
  renderWithClient(<Overview />)
  const nvda = await screen.findByRole('row', { name: /NVDA/ })
  expect(within(nvda).getByLabelText('Your reason is being challenged')).toBeInTheDocument()
})


test('dashboard shows stat tiles, attention list, top exposures and value columns', async () => {
  server.use(
    http.get('/api/lists', () =>
      HttpResponse.json({
        holdings: [
          row({ ticker: 'NVDA', lean: 'bullish', price: 200, day_change_pct: -4, shares: 10, thesis_verdict: 'challenges' }),
          row({ ticker: 'QQQ', kind: 'etf', lean: 'neutral', price: 600, day_change_pct: 2, shares: 5 }),
        ],
        watching: [],
      }),
    ),
    http.get('/api/exposure', () =>
      HttpResponse.json({
        total_value: 5000,
        positions: [
          { ticker: 'NVDA', shares: 10, price: 200, value: 2000, weight: 0.4, name: 'NVIDIA', kind: 'stock' },
          { ticker: 'QQQ', shares: 5, price: 600, value: 3000, weight: 0.6, name: 'QQQ', kind: 'etf' },
        ],
        underlying: [{ symbol: 'NVDA', name: 'NVIDIA Corporation', weight: 0.46, direct: 0.4, via: { QQQ: 0.06 } }],
        rest_of_funds: 0.49, sectors: [], missing_prices: [],
      }),
    ),
  )
  renderWithClient(<Overview />)
  const tiles = await screen.findByRole('region', { name: 'Portfolio summary' })
  expect(await within(tiles).findByText('$5,000.00')).toBeInTheDocument()
  const attention = screen.getByRole('region', { name: 'Needs attention' })
  expect(within(attention).getByText(/Your reason is being challenged/)).toBeInTheDocument()
  const top = screen.getByRole('region', { name: 'Top real exposures' })
  expect(within(top).getByText('46.0%')).toBeInTheDocument()
  const nvda = screen.getByRole('row', { name: /NVDA NVIDIA|^NVDA/ })
  expect(within(nvda).getByText('$2,000.00')).toBeInTheDocument()
  expect(within(nvda).getByText('40.0%')).toBeInTheDocument()
})

const mv = (o: Record<string, unknown>) =>
  row({ move_date: '2026-11-05', move_notable: false, move_change_pct: 0.3, move_typical_pct: 1, ...o })

function serveLists(holdings: unknown[], watching: unknown[] = []) {
  server.use(http.get('/api/lists', () => HttpResponse.json({ holdings, watching })))
}

test('biggest moves lists unusual movers with reasons and opens a reading', async () => {
  serveLists(
    [
      mv({ ticker: 'NVDA', move_notable: true, move_change_pct: -9.3, move_typical_pct: 2.5, market_change_pct: -4.4, move_reason: 'Chip sell-off on spending fears' }),
      mv({ ticker: 'VOO', kind: 'etf', market_notable: true }),
    ],
    [
      mv({ ticker: 'META', move_notable: true, move_change_pct: -4.0, move_typical_pct: 1.5, market_change_pct: -4.4 }),
      mv({ ticker: 'TSLA', move_notable: true, move_change_pct: -6.0, move_typical_pct: 1.0, market_change_pct: -4.4, ai_status: 'budget_exhausted' }),
      mv({ ticker: 'AAPL', move_date: '2026-10-29', move_notable: true, move_change_pct: -5 }),
    ],
  )
  renderWithClient(<Overview />)
  const card = await screen.findByRole('region', { name: 'Biggest moves' })
  expect(within(card).getByText('S&P 500 down 4.4% on Thu Nov 5 — a big day for the whole market')).toBeInTheDocument()
  const rows = within(card).getAllByRole('button')
  expect(rows.map((r) => r.textContent)).toEqual([
    expect.stringContaining('TSLA'),
    expect.stringContaining('NVDA'),
    expect.stringContaining('META'),
  ])
  expect(within(rows[0]).getByText('AI read not available')).toBeInTheDocument()
  expect(within(rows[1]).getByText('-9.3%')).toBeInTheDocument()
  expect(within(rows[1]).getByText('Chip sell-off on spending fears')).toBeInTheDocument()
  expect(within(rows[2]).getByText('About the same as the market; no company-specific news found')).toBeInTheDocument()
  expect(within(card).getByText('1 ticker not refreshed for this day')).toBeInTheDocument()
  await userEvent.click(rows[1])
  expect(useSelection.getState().selected).toBe('NVDA')
})

test('biggest moves: no unusual moves, and plain header without a big market day', async () => {
  serveLists([mv({ ticker: 'NVDA', market_change_pct: -0.2 })])
  renderWithClient(<Overview />)
  const card = await screen.findByRole('region', { name: 'Biggest moves' })
  expect(within(card).getByText('S&P 500 down 0.2% on Thu Nov 5')).toBeInTheDocument()
  expect(within(card).getByText('No unusual moves on the last trading day.')).toBeInTheDocument()
})

test('biggest moves: a notable row without a reason and unlike the market', async () => {
  serveLists([mv({ ticker: 'NVDA', move_notable: true, move_change_pct: -9, market_change_pct: -1 })])
  renderWithClient(<Overview />)
  const card = await screen.findByRole('region', { name: 'Biggest moves' })
  expect(within(card).getByText('No company-specific news found')).toBeInTheDocument()
})

test('biggest moves is hidden until readings have move data', async () => {
  serveLists([row({ ticker: 'NVDA' })])
  renderWithClient(<Overview />)
  await screen.findByRole('row', { name: /NVDA/ })
  expect(screen.queryByRole('region', { name: 'Biggest moves' })).not.toBeInTheDocument()
})
