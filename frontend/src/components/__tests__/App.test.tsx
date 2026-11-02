import { vi } from 'vitest'
vi.mock('lightweight-charts', () => ({
  createChart: () => ({ addSeries: () => ({ setData: () => {} }), timeScale: () => ({ fitContent: () => {} }), remove: () => {} }),
  LineSeries: {},
}))
import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import App from '../../App'
import { renderWithClient } from '../../test/utils'

test('shows the disclaimer and brand', () => {
  renderWithClient(<App />)
  expect(screen.getByText('Kairos is a research tool, not financial advice.')).toBeInTheDocument()
  expect(screen.getByText('KAIROS')).toBeInTheDocument()
})

test('a reading links to its own track record', async () => {
  const { http, HttpResponse } = await import('msw')
  const { server } = await import('../../test/server')
  const { reading } = await import('../../test/fixtures/reading')
  const { useSelection } = await import('../../store/selection')
  const userEvent = (await import('@testing-library/user-event')).default
  let askedFor: string | null = null
  const empty = { n: 0, avg_change_pct: null, avg_excess_pct: null, pct_positive: null }
  const h = { '1': empty, '5': empty, '20': empty }
  server.use(
    http.get('/api/readings/NVDA', () => HttpResponse.json(reading)),
    http.get('/api/track-record', ({ request }) => {
      askedFor = new URL(request.url).searchParams.get('ticker')
      return HttpResponse.json({ by_lean: { bullish: h, neutral: h, bearish: h }, small_sample: true })
    }),
  )
  useSelection.getState().select('NVDA')
  renderWithClient(<App />)
  await userEvent.click(await screen.findByRole('button', { name: 'Track record for NVDA' }))
  expect(await screen.findByRole('heading', { name: 'Track record — NVDA' })).toBeInTheDocument()
  expect(askedFor).toBe('NVDA')
})
