import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { beforeEach, expect, test, vi } from 'vitest'
import type { Reading } from '../../api/schemas'
import { useSelection } from '../../store/selection'
import { reading } from '../../test/fixtures/reading'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { ComparePage } from '../ComparePage'

vi.mock('lightweight-charts', () => ({
  createChart: () => ({
    addSeries: () => ({ setData: () => {} }),
    timeScale: () => ({ fitContent: () => {}, setVisibleLogicalRange: () => {} }),
    remove: () => {},
  }),
  LineSeries: {},
}))

const etf = (ticker: string, expense: number, holdings: { symbol: string; weight: number }[]): Reading => ({
  ...reading,
  ticker,
  name: `${ticker} fund`,
  kind: 'etf',
  quick: {
    ...reading.quick,
    kind: 'etf',
    market_cap: null,
    trailing_pe: null,
    expense_ratio: expense,
    aum: 5e11,
    top_holdings: holdings.map((h) => ({ ...h, name: h.symbol })),
  },
})

function serve(readings: Record<string, Reading>) {
  for (const [t, r] of Object.entries(readings)) {
    server.use(http.get(`/api/readings/${t}`, () => HttpResponse.json(r)))
  }
}

beforeEach(() => useSelection.setState({ compare: [null, null] }))

test('two ETFs side by side: cheaper fee highlighted and holdings overlap shown', async () => {
  serve({
    QQQ: etf('QQQ', 0.002, [{ symbol: 'NVDA', weight: 0.09 }, { symbol: 'MSFT', weight: 0.08 }]),
    VOO: etf('VOO', 0.0003, [{ symbol: 'NVDA', weight: 0.07 }, { symbol: 'AAPL', weight: 0.06 }]),
  })
  useSelection.setState({ compare: ['QQQ', 'VOO'] })
  renderWithClient(<ComparePage />)
  const fees = await screen.findByRole('row', { name: /Expense ratio/ })
  expect(within(fees).getByText('0.03%')).toHaveClass('better')
  expect(within(fees).getByText('0.20%')).not.toHaveClass('better')
  expect(screen.getByText(/7\.0% of top-10 holdings overlap/)).toBeInTheDocument()
  expect(screen.getByText(/Shared: NVDA/)).toBeInTheDocument()
})

test('stock vs ETF shows — where a row does not apply', async () => {
  serve({ NVDA: reading, VOO: etf('VOO', 0.0003, []) })
  useSelection.setState({ compare: ['NVDA', 'VOO'] })
  renderWithClient(<ComparePage />)
  const pe = await screen.findByRole('row', { name: /P\/E/ })
  expect(within(pe).getByText('25.9')).toBeInTheDocument()
  expect(within(pe).getByText('—')).toBeInTheDocument()
})

test('same ticker twice asks for two different tickers', () => {
  useSelection.setState({ compare: ['VOO', 'VOO'] })
  renderWithClient(<ComparePage />)
  expect(screen.getByText('Pick two different tickers.')).toBeInTheDocument()
})

test('with only one ticker the page explains what to do next', async () => {
  serve({ QQQ: etf('QQQ', 0.002, []) })
  useSelection.setState({ compare: ['QQQ', null] })
  renderWithClient(<ComparePage />)
  expect(await screen.findByText('Enter a second ticker to compare.')).toBeInTheDocument()
})

test('with no tickers the page explains what to do', () => {
  renderWithClient(<ComparePage />)
  expect(screen.getByText('Enter two tickers to compare them side by side.')).toBeInTheDocument()
})
