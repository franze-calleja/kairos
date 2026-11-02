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
