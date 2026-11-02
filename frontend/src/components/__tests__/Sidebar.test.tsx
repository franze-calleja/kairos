import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'
import { useSelection } from '../../store/selection'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { Sidebar } from '../Sidebar'

const empty = {
  name: null, kind: null, price: null, day_change_pct: null, price_label: null,
  next_earnings: null, hype_warning: null, updated_at: null,
}
const lists = {
  holdings: [
    { ...empty, ticker: 'NVDA', lean: 'bullish', ai_status: 'ok', price: 204.64, day_change_pct: -4.2 },
    { ...empty, ticker: 'VOO', lean: null, ai_status: null },
  ],
  watching: [{ ...empty, ticker: 'TINY', lean: null, ai_status: 'not_enough_signal' }],
}

test('shows lists with lean pills', async () => {
  server.use(http.get('/api/lists', () => HttpResponse.json(lists)))
  renderWithClient(<Sidebar />)
  const nvda = await screen.findByRole('button', { name: /^NVDA/ })
  expect(within(nvda).getByText('Bullish')).toBeInTheDocument()
  expect(within(nvda).getByText('-4.2%')).toBeInTheDocument()
  expect(within(screen.getByRole('button', { name: /^VOO/ })).getByText('No reading yet')).toBeInTheDocument()
  expect(
    within(screen.getByRole('button', { name: /^TINY/ })).getByText('Not enough signal'),
  ).toBeInTheDocument()
})

test('clicking a ticker selects it', async () => {
  server.use(http.get('/api/lists', () => HttpResponse.json(lists)))
  renderWithClient(<Sidebar />)
  await userEvent.click(await screen.findByRole('button', { name: /^NVDA/ }))
  expect(useSelection.getState().selected).toBe('NVDA')
})

test('adding a ticker posts it to the list', async () => {
  let body: unknown = null
  server.use(
    http.post('/api/lists/watching', async ({ request }) => {
      body = await request.json()
      return HttpResponse.json({ ticker: 'SMH', lean: null, ai_status: null }, { status: 201 })
    }),
  )
  renderWithClient(<Sidebar />)
  await userEvent.type(screen.getByLabelText('Add to Watching'), 'smh{Enter}')
  await screen.findByLabelText('Add to Watching')
  expect(body).toEqual({ ticker: 'smh' })
})

test('add error shows the backend detail', async () => {
  server.use(
    http.post('/api/lists/holdings', () =>
      HttpResponse.json({ detail: 'Invalid ticker: a;b' }, { status: 422 }),
    ),
  )
  renderWithClient(<Sidebar />)
  await userEvent.type(screen.getByLabelText('Add to My Holdings'), 'a;b{Enter}')
  expect(await screen.findByText('Invalid ticker: a;b')).toBeInTheDocument()
})

test('discover rows show why they were suggested', async () => {
  server.use(
    http.get('/api/discover', () =>
      HttpResponse.json({
        items: [{ ticker: 'SMH', reason: 'holds NVDA (20.0%)', score: 2 }],
        created_at: '2026-11-02T00:00:00Z',
        spike_scan: 'ok',
      }),
    ),
  )
  renderWithClient(<Sidebar />)
  expect(await screen.findByText('holds NVDA (20.0%)')).toBeInTheDocument()
})


test('discover shows scan progress while the morning refresh scans', async () => {
  server.use(
    http.get('/api/jobs/morning', () =>
      HttpResponse.json({
        running: true, phase: 'discover', done: 120, total: 503, current: null,
        started_at: null, last_run: null,
      }),
    ),
  )
  renderWithClient(<Sidebar />)
  expect(await screen.findByText('Scanning S&P 500… 120 / 503')).toBeInTheDocument()
})
