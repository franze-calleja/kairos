import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'
import { useSelection } from '../../store/selection'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { ExposurePage } from '../ExposurePage'

const entry = (o: Record<string, unknown>) => ({
  lean: null, ai_status: null, name: null, kind: null, price: null, day_change_pct: null,
  price_label: null, next_earnings: null, hype_warning: null, updated_at: null,
  shares: null, thesis: null, thesis_verdict: null, ...o,
})

const exposure = {
  total_value: 5000,
  positions: [
    { ticker: 'QQQ', shares: 5, price: 600, value: 3000, weight: 0.6, name: 'Invesco QQQ Trust', kind: 'etf' },
    { ticker: 'NVDA', shares: 10, price: 200, value: 2000, weight: 0.4, name: 'NVIDIA Corporation', kind: 'stock' },
  ],
  underlying: [
    { symbol: 'NVDA', name: 'NVIDIA Corporation', weight: 0.46, direct: 0.4, via: { QQQ: 0.06 } },
    { symbol: 'MSFT', name: 'Microsoft Corporation', weight: 0.048, direct: 0, via: { QQQ: 0.048 } },
  ],
  rest_of_funds: 0.492,
  sectors: [
    { sector: 'Technology', weight: 0.7 },
    { sector: 'Communication Services', weight: 0.3 },
  ],
  missing_prices: [] as string[],
}

function serve(exp = exposure, holdings = [entry({ ticker: 'NVDA', shares: 10 }), entry({ ticker: 'QQQ', shares: 5 })]) {
  server.use(
    http.get('/api/exposure', () => HttpResponse.json(exp)),
    http.get('/api/lists', () => HttpResponse.json({ holdings, watching: [] })),
  )
}

test('shows real exposure with look-through, rest of funds and sectors', async () => {
  serve()
  renderWithClient(<ExposurePage />)
  const table = await screen.findByRole('table', { name: 'What you really own' })
  const nvda = within(table).getByRole('row', { name: /NVDA/ })
  expect(within(nvda).getByText('46.0%')).toBeInTheDocument()
  expect(within(nvda).getByText('via QQQ 6.0%')).toBeInTheDocument()
  expect(within(table).getByRole('row', { name: /Rest of funds/ })).toHaveTextContent('49.2%')
  expect(screen.getByText('Technology')).toBeInTheDocument()
  expect(screen.getByText('70.0%')).toBeInTheDocument()
  expect(screen.getByText('$5,000.00')).toBeInTheDocument()
})

test('editing shares saves them', async () => {
  serve()
  let body: unknown = null
  server.use(
    http.put('/api/lists/holdings/NVDA/shares', async ({ request }) => {
      body = await request.json()
      return HttpResponse.json(entry({ ticker: 'NVDA', shares: 12 }))
    }),
  )
  renderWithClient(<ExposurePage />)
  const input = await screen.findByLabelText('Shares of NVDA')
  await userEvent.clear(input)
  await userEvent.type(input, '12{Enter}')
  await screen.findByLabelText('Shares of NVDA')
  expect(body).toEqual({ shares: 12 })
})

test('empty state explains what to enter', async () => {
  serve({ ...exposure, total_value: 0, positions: [], underlying: [], rest_of_funds: 0, sectors: [] }, [entry({ ticker: 'NVDA' })])
  renderWithClient(<ExposurePage />)
  expect(await screen.findByText('Enter how many shares you own to see your real exposure.')).toBeInTheDocument()
})

test('lists holdings without a price', async () => {
  serve({ ...exposure, missing_prices: ['ZZZZ'] })
  renderWithClient(<ExposurePage />)
  expect(await screen.findByText(/No price for ZZZZ/)).toBeInTheDocument()
})

test('invalid share input is rejected with a message, not silently dropped', async () => {
  serve()
  let calls = 0
  server.use(
    http.put('/api/lists/holdings/NVDA/shares', () => {
      calls += 1
      return HttpResponse.json(entry({ ticker: 'NVDA', shares: 10 }))
    }),
  )
  renderWithClient(<ExposurePage />)
  const input = await screen.findByLabelText('Shares of NVDA')
  await userEvent.clear(input)
  await userEvent.type(input, '12,5{Enter}')
  expect(await screen.findByText('Enter a number like 12.5')).toBeInTheDocument()
  await userEvent.clear(input)
  await userEvent.type(input, 'Infinity{Enter}')
  expect(calls).toBe(0)
})

test('holdings with logged buys show their shares read-only with a link to My buys', async () => {
  serve(exposure, [
    entry({ ticker: 'NVDA', shares: 0.3268, shares_source: 'trades' }),
    entry({ ticker: 'QQQ', shares: 5, shares_source: 'manual' }),
  ])
  renderWithClient(<ExposurePage />)
  const link = await screen.findByRole('button', { name: '0.3268 · from My buys' })
  expect(screen.queryByRole('textbox', { name: 'Shares of NVDA' })).not.toBeInTheDocument()
  expect(screen.queryByRole('spinbutton', { name: 'Shares of NVDA' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('Shares of QQQ')).toBeInTheDocument()
  await userEvent.click(link)
  expect(useSelection.getState().view).toBe('buys')
})
