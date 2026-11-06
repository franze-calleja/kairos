import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'
import { emptyPortfolio } from '../../test/handlers'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { AddTradeForm } from '../AddTradeForm'
import { nyToday } from '../buys'

function serveClose(close = 181.6, date = '2026-11-06') {
  const asked: string[] = []
  server.use(
    http.get('/api/prices/:ticker/close', ({ params, request }) => {
      asked.push(`${params.ticker}@${new URL(request.url).searchParams.get('date')}`)
      return HttpResponse.json({ date, close })
    }),
  )
  return asked
}

function captureTrades(status = 201, detail = '') {
  const sent: unknown[] = []
  server.use(
    http.post('/api/trades', async ({ request }) => {
      const body = await request.json()
      sent.push(body)
      return status === 201
        ? HttpResponse.json({ id: 1, ticker: 'NVDA', side: 'buy', trade_date: '2026-11-06', shares: 0.1, price: 181.6, created_at: '2026-11-06T00:00:00Z' }, { status })
        : HttpResponse.json({ detail }, { status })
    }),
  )
  return sent
}

const ticker = () => screen.getByRole('textbox', { name: 'Ticker' })
const amount = () => screen.getByRole('spinbutton', { name: 'Amount in dollars' })
const price = () => screen.getByRole('spinbutton', { name: 'Price per share' })

test('date defaults to today in New York with the US-date hint', () => {
  renderWithClient(<AddTradeForm />)
  expect(screen.getByLabelText('US trade date')).toHaveValue(nyToday())
  expect(screen.getByText('Bought after midnight your time? Use the previous day (US date).')).toBeInTheDocument()
})

test("price is pre-filled with that day's close and the share preview updates", async () => {
  const asked = serveClose()
  renderWithClient(<AddTradeForm />)
  await userEvent.type(ticker(), 'nvda')
  await userEvent.tab()
  await waitFor(() => expect(price()).toHaveValue(181.6))
  expect(asked).toEqual([`NVDA@${nyToday()}`])
  expect(screen.getByText('(close on Fri Nov 6)')).toBeInTheDocument()
  await userEvent.type(amount(), '25')
  expect(screen.getByText('= 0.1377 shares')).toBeInTheDocument()
})

test('saving a buy by amount keeps ticker and date and clears the amount', async () => {
  serveClose()
  const sent = captureTrades()
  renderWithClient(<AddTradeForm />)
  await userEvent.type(ticker(), 'nvda')
  await userEvent.tab()
  await waitFor(() => expect(price()).toHaveValue(181.6))
  await userEvent.type(amount(), '25')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(sent).toHaveLength(1))
  expect(sent[0]).toEqual({ ticker: 'NVDA', side: 'buy', date: nyToday(), amount: 25, price: 181.6 })
  await waitFor(() => expect(amount()).toHaveValue(null))
  expect(ticker()).toHaveValue('nvda')
})

test('shares mode sends shares', async () => {
  serveClose()
  const sent = captureTrades()
  renderWithClient(<AddTradeForm />)
  await userEvent.type(ticker(), 'NVDA')
  await userEvent.tab()
  await waitFor(() => expect(price()).toHaveValue(181.6))
  await userEvent.click(screen.getByRole('button', { name: 'Shares' }))
  await userEvent.type(screen.getByRole('spinbutton', { name: 'Shares' }), '2')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(sent[0]).toMatchObject({ shares: 2 }))
  expect(sent[0]).not.toHaveProperty('amount')
})

test('sell all fills the exact held shares and server errors are shown', async () => {
  serveClose()
  server.use(
    http.get('/api/portfolio', () =>
      HttpResponse.json({
        ...emptyPortfolio,
        positions: [
          { ticker: 'NVDA', shares: 0.326842, avg_cost: 198.9, invested: 65, value: 59.34, gain: -5.66, gain_pct: -8.7, realized: 0, total_bought: 65, sell_proceeds: 0, return_pct: -8.7, voo_pct: 1.2 },
        ],
      }),
    ),
  )
  const sent = captureTrades(422, 'You only held 0 NVDA on 2026-11-06')
  renderWithClient(<AddTradeForm />)
  await userEvent.click(screen.getByRole('button', { name: 'Sell' }))
  await userEvent.type(ticker(), 'NVDA')
  await userEvent.tab()
  await userEvent.click(await screen.findByRole('button', { name: 'Sell all' }))
  expect(screen.getByRole('spinbutton', { name: 'Shares' })).toHaveValue(0.326842)
  await waitFor(() => expect(price()).toHaveValue(181.6))
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(sent[0]).toMatchObject({ side: 'sell', shares: 0.326842 }))
  expect(await screen.findByText('You only held 0 NVDA on 2026-11-06')).toBeInTheDocument()
})

test('a typed price is not overwritten by the close lookup', async () => {
  serveClose()
  renderWithClient(<AddTradeForm />)
  await userEvent.type(ticker(), 'NVDA')
  await userEvent.tab()
  await waitFor(() => expect(price()).toHaveValue(181.6))
  await userEvent.clear(price())
  await userEvent.type(price(), '180.25')
  await new Promise((r) => setTimeout(r, 50))
  expect(price()).toHaveValue(180.25)
})

function servePerTicker(closes: Record<string, number>) {
  server.use(
    http.get('/api/prices/:ticker/close', ({ params }) =>
      HttpResponse.json({ date: '2026-11-06', close: closes[String(params.ticker)] }),
    ),
  )
}

test('changing the ticker and pressing Enter loads its price instead of saving with the old one', async () => {
  servePerTicker({ NVDA: 181.6, QQQ: 647.05 })
  const sent = captureTrades()
  renderWithClient(<AddTradeForm />)
  await userEvent.type(ticker(), 'NVDA')
  await userEvent.tab()
  await waitFor(() => expect(price()).toHaveValue(181.6))
  await userEvent.type(amount(), '25')
  await userEvent.clear(ticker())
  await userEvent.type(ticker(), 'QQQ{Enter}')
  await waitFor(() => expect(price()).toHaveValue(647.05))
  expect(sent).toHaveLength(0)
  expect(screen.getByText('Got the price for QQQ. Check it, then press Save.')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(sent[0]).toMatchObject({ ticker: 'QQQ', price: 647.05 }))
})

test('changing the date keeps a price you typed', async () => {
  serveClose()
  renderWithClient(<AddTradeForm />)
  await userEvent.type(ticker(), 'NVDA')
  await userEvent.tab()
  await waitFor(() => expect(price()).toHaveValue(181.6))
  await userEvent.clear(price())
  await userEvent.type(price(), '180.25')
  await userEvent.clear(screen.getByLabelText('US trade date'))
  await userEvent.type(screen.getByLabelText('US trade date'), '2026-11-05')
  expect(price()).toHaveValue(180.25)
})

test('closes are rounded to cents in the form and when saved', async () => {
  serveClose(181.6000061)
  const sent = captureTrades()
  renderWithClient(<AddTradeForm />)
  await userEvent.type(ticker(), 'NVDA')
  await userEvent.tab()
  await waitFor(() => expect(price()).toHaveValue(181.6))
  await userEvent.type(amount(), '25')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(sent[0]).toMatchObject({ price: 181.6 }))
})
