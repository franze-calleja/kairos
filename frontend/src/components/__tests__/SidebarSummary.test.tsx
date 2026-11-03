import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'
import { useSelection } from '../../store/selection'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { SidebarSummary } from '../SidebarSummary'

const e = (o: Record<string, unknown>) => ({
  lean: null, ai_status: 'ok', name: null, kind: 'stock', price: null, day_change_pct: null, price_label: null,
  next_earnings: null, hype_warning: false, updated_at: null, shares: null, thesis: null, thesis_verdict: null, ...o,
})

function serve(withShares: boolean) {
  server.use(
    http.get('/api/lists', () =>
      HttpResponse.json({
        holdings: [
          e({ ticker: 'NVDA', lean: 'bullish', day_change_pct: -4, shares: withShares ? 10 : null, thesis_verdict: 'challenges' }),
          e({ ticker: 'QQQ', kind: 'etf', lean: 'neutral', day_change_pct: 2, shares: withShares ? 5 : null }),
        ],
        watching: [e({ ticker: 'GOOGL', lean: 'bearish' })],
      }),
    ),
    http.get('/api/exposure', () =>
      HttpResponse.json({
        total_value: withShares ? 5000 : 0,
        positions: withShares
          ? [
              { ticker: 'NVDA', shares: 10, price: 200, value: 2000, weight: 0.4, name: 'NVIDIA', kind: 'stock' },
              { ticker: 'QQQ', shares: 5, price: 600, value: 3000, weight: 0.6, name: 'QQQ', kind: 'etf' },
            ]
          : [],
        underlying: [], rest_of_funds: 0, sectors: [], missing_prices: [],
      }),
    ),
  )
}

test('shows portfolio value, today, lean mix and what needs attention', async () => {
  serve(true)
  renderWithClient(<SidebarSummary />)
  const card = await screen.findByRole('region', { name: 'At a glance' })
  expect(await within(card).findByText('$5,000.00')).toBeInTheDocument()
  expect(within(card).getByText('-$24.51 (-0.49%) today')).toBeInTheDocument()
  expect(within(card).getByText('1 bullish')).toBeInTheDocument()
  expect(within(card).getByText('1 bearish')).toBeInTheDocument()
  expect(within(card).getByText(/Next refresh/)).toBeInTheDocument()
  await userEvent.click(within(card).getByRole('button', { name: /NVDA.*Your reason is being challenged/ }))
  expect(useSelection.getState().selected).toBe('NVDA')
})

test('without share counts it points to Exposure', async () => {
  serve(false)
  renderWithClient(<SidebarSummary />)
  await userEvent.click(await screen.findByRole('button', { name: 'Add share counts to see your portfolio value' }))
  expect(useSelection.getState().view).toBe('exposure')
})
