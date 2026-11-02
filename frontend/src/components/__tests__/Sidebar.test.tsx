import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'
import { useSelection } from '../../store/selection'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { Sidebar } from '../Sidebar'

const lists = {
  holdings: [
    { ticker: 'NVDA', lean: 'bullish', ai_status: 'ok' },
    { ticker: 'VOO', lean: null, ai_status: null },
  ],
  watching: [{ ticker: 'TINY', lean: null, ai_status: 'not_enough_signal' }],
}

test('shows lists with lean pills', async () => {
  server.use(http.get('/api/lists', () => HttpResponse.json(lists)))
  renderWithClient(<Sidebar />)
  const nvda = await screen.findByRole('button', { name: /^NVDA/ })
  expect(within(nvda).getByText('Bullish')).toBeInTheDocument()
  expect(within(screen.getByRole('button', { name: /^VOO/ })).getByText('—')).toBeInTheDocument()
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
