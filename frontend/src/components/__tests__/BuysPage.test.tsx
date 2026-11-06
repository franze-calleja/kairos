import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { BuysPage } from '../BuysPage'

test('empty state explains what logging buys gives you', async () => {
  renderWithClient(<BuysPage />)
  expect(
    await screen.findByText('Log your buys to see your average cost, gains and how they compare with simply buying VOO.'),
  ).toBeInTheDocument()
  expect(
    screen.getByText('Already own some? Log it as one buy at your average price (Gotrade shows it on the position).'),
  ).toBeInTheDocument()
})

const position = {
  ticker: 'QQQ', shares: 0.33481, avg_cost: 610.2, invested: 204.3, value: 216.74, gain: 12.44, gain_pct: 6.09,
  realized: 0, total_bought: 204.3, sell_proceeds: 0, return_pct: 6.09, voo_pct: 3.9,
}
const portfolio = {
  positions: [position, { ...position, ticker: 'VOO', voo_pct: null, gain: -1, gain_pct: -0.5 }],
  totals: { invested: 454.34, value: 466.48, gain: 12.14, return_pct: 2.7, voo_pct: 2.8 },
  realized: 7.5,
  history: [
    { id: 7, ticker: 'NVDA', side: 'buy', trade_date: '2026-10-14', shares: 0.19, price: 210.3, amount: 40, kairos_said: { price_label: 'near_average', lean: 'bullish', ai_status: 'ok' }, since_pct: -13.6, voo_since_pct: -2.9 },
    { id: 6, ticker: 'VOO', side: 'buy', trade_date: '2026-09-03', shares: 0.15, price: 642.8, amount: 100, kairos_said: null, since_pct: 4.9, voo_since_pct: 4.9 },
  ],
}

function servePortfolio() {
  server.use(http.get('/api/portfolio', () => HttpResponse.json(portfolio)))
}

test('positions table shows costs, gains and the VOO comparison', async () => {
  servePortfolio()
  renderWithClient(<BuysPage />)
  const table = await screen.findByRole('table', { name: 'Your positions' })
  const headers = within(table).getAllByRole('columnheader').map((h) => h.textContent)
  expect(headers).toEqual(['Ticker', 'Shares', 'Avg cost', 'Invested', 'Value now', 'Gain', 'Your return', 'Same $ in VOO'])
  const qqq = within(table).getByRole('row', { name: /QQQ/ })
  expect(within(qqq).getByText('0.3348')).toBeInTheDocument()
  expect(within(qqq).getByText('+$12.44 (+6.1%)')).toBeInTheDocument()
  expect(within(qqq).getByText('+3.9%')).toBeInTheDocument()
  expect(within(within(table).getByRole('row', { name: /^VOO/ })).getByText('—')).toBeInTheDocument()
  expect(within(table).getByRole('row', { name: /Total/ })).toHaveTextContent('+$12.14 (+2.7%)')
  expect(screen.getByText('Realized from sales: +$7.50')).toBeInTheDocument()
})

test('history shows what Kairos said and the change since vs VOO', async () => {
  servePortfolio()
  renderWithClient(<BuysPage />)
  const table = await screen.findByRole('table', { name: 'Buy history' })
  const nvda = within(table).getByRole('row', { name: /NVDA/ })
  expect(within(nvda).getByText('Near long-term avg')).toBeInTheDocument()
  expect(within(nvda).getByText('Bullish')).toBeInTheDocument()
  expect(within(nvda).getByText('-13.6% (VOO -2.9%)')).toBeInTheDocument()
  expect(within(within(table).getByRole('row', { name: /^Sep 3/ })).getByText('no reading that day')).toBeInTheDocument()
})

test('delete asks inline, then deletes; a refusal is shown', async () => {
  servePortfolio()
  const deleted: string[] = []
  server.use(
    http.delete('/api/trades/:id', ({ params }) => {
      deleted.push(String(params.id))
      return params.id === '7'
        ? new HttpResponse(null, { status: 204 })
        : HttpResponse.json({ detail: "Can't delete this buy" }, { status: 422 })
    }),
  )
  renderWithClient(<BuysPage />)
  const table = await screen.findByRole('table', { name: 'Buy history' })
  const nvda = within(table).getByRole('row', { name: /NVDA/ })
  await userEvent.click(within(nvda).getByRole('button', { name: 'Delete' }))
  expect(within(nvda).getByText('Delete?')).toBeInTheDocument()
  await userEvent.click(within(nvda).getByRole('button', { name: 'Yes' }))
  await waitFor(() => expect(deleted).toEqual(['7']))
  const voo = within(table).getByRole('row', { name: /^Sep 3/ })
  await userEvent.click(within(voo).getByRole('button', { name: 'Delete' }))
  await userEvent.click(within(voo).getByRole('button', { name: 'Yes' }))
  expect(await screen.findByText("Can't delete this buy")).toBeInTheDocument()
})
