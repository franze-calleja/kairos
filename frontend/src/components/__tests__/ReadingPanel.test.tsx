import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expect, test, vi } from 'vitest'
import type { Reading } from '../../api/schemas'
import { reading } from '../../test/fixtures/reading'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { ReadingPanel } from '../ReadingPanel'

const ranges: { from: number; to: number }[] = []
vi.mock('lightweight-charts', () => ({
  createChart: () => ({
    addSeries: () => ({ setData: () => {} }),
    timeScale: () => ({
      fitContent: () => {},
      setVisibleLogicalRange: (r: { from: number; to: number }) => ranges.push(r),
    }),
    applyOptions: () => {},
    remove: () => {},
  }),
  LineSeries: {},
}))

function serve(r: Partial<Reading>) {
  server.use(http.get('/api/readings/NVDA', () => HttpResponse.json({ ...reading, ...r })))
}

test('full reading renders all sections with cited sources', async () => {
  serve({})
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  expect(await screen.findByRole('heading', { name: "What's driving it" })).toBeInTheDocument()
  for (const name of ['Bull case', 'Bear case', 'Should I add more?', 'Upcoming events', 'Hype check', 'Quick numbers', 'Sources', 'Data health']) {
    expect(screen.getByRole('heading', { name })).toBeInTheDocument()
  }
  const drivers = screen.getByRole('heading', { name: "What's driving it" }).closest('section')!
  expect(within(drivers).getByRole('link', { name: '[1]' })).toHaveAttribute('href', 'https://example.com/guidance')
  expect(screen.getAllByText('Earnings in 5 days').length).toBeGreaterThan(0)
  expect(screen.getAllByText('Near its long-term average').length).toBeGreaterThan(0)
  expect(screen.getAllByText('No warning signs').length).toBeGreaterThan(0)
  const verdict = screen.getByRole('region', { name: 'Verdict' })
  expect(within(verdict).getByText('Bullish')).toBeInTheDocument()
  expect(within(verdict).getByText('Demand is strong but export rules are the risk to watch')).toBeInTheDocument()
  expect(within(verdict).queryByText('Data-center guidance raised')).toBeNull()
})

test('not_enough_signal hides AI cards but shows numbers', async () => {
  serve({ ai: null, ai_status: 'not_enough_signal' })
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  expect(await screen.findByText(/Not enough signal: too little recent coverage/)).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Bull case' })).toBeNull()
  expect(screen.getByRole('heading', { name: 'Should I add more?' })).toBeInTheDocument()
})

test('budget_exhausted banner keeps computed sections', async () => {
  serve({ ai: null, ai_status: 'budget_exhausted' })
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  expect(await screen.findByText('AI request limit reached. Numbers below are still current.')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Quick numbers' })).toBeInTheDocument()
})

test('not_configured explains how to enable AI', async () => {
  serve({ ai: null, ai_status: 'not_configured' })
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  expect(await screen.findByText('Add GEMINI_API_KEY to .env to enable AI summaries.')).toBeInTheDocument()
})

test('unknown ticker message', async () => {
  server.use(http.get('/api/readings/XYZQQ', () => HttpResponse.json({ detail: 'Unknown ticker: XYZQQ' }, { status: 404 })))
  renderWithClient(<ReadingPanel ticker="XYZQQ" />)
  expect(await screen.findByText('Unknown ticker: XYZQQ')).toBeInTheDocument()
})

test('source links are safe', async () => {
  serve({})
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  const sources = (await screen.findByRole('heading', { name: 'Sources' })).closest('section')!
  const links = within(sources).getAllByRole('link')
  expect(links).toHaveLength(2)
  for (const link of links) {
    expect(link).toHaveAttribute('target', '_blank')
    expect(link.getAttribute('rel')).toContain('noopener')
  }
})

test('triggered hype flags show a warning', async () => {
  serve({
    hype: reading.hype.map((f) => (f.code === 'otc' ? { ...f, triggered: true, value: 'exchange: PNK' } : f)),
  })
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  expect(await screen.findByText('exchange: PNK')).toBeInTheDocument()
  expect(screen.getByText('Hype warning')).toBeInTheDocument()
})

test('passed hype checks use neutral labels, not warning wording', async () => {
  serve({})
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  const card = (await screen.findByRole('heading', { name: 'Hype check' })).closest('section')!
  const userEvent = (await import('@testing-library/user-event')).default
  await userEvent.click(within(card).getByRole('button', { name: /6 checks passed/ }))
  for (const label of ['Company size', 'Share price', 'Exchange', 'Trading volume', '5-day price move', 'Buzz vs. real news']) {
    expect(within(card).getByText(new RegExp(label))).toBeInTheDocument()
  }
  for (const warning of ['Very small company', 'Penny stock price', 'Thinly traded', 'Not on a major exchange']) {
    expect(within(card).queryByText(new RegExp(warning))).toBeNull()
  }
})

test('triggered hype checks use warning wording', async () => {
  serve({
    hype: reading.hype.map((f) => (f.code === 'penny' ? { ...f, triggered: true, value: '$1.20 share price' } : f)),
  })
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  const card = (await screen.findByRole('heading', { name: 'Hype check' })).closest('section')!
  expect(within(card).getByText(/Penny stock price/)).toBeInTheDocument()
  expect(within(card).queryByText(/Share price/)).toBeNull()
})

test('refresh shows progress, then confirms the update', async () => {
  const { delay } = await import('msw')
  const userEvent = (await import('@testing-library/user-event')).default
  server.use(
    http.get('/api/readings/NVDA', async ({ request }) => {
      if (new URL(request.url).searchParams.get('refresh')) {
        await delay(150)
        return HttpResponse.json({ ...reading, created_at: '2026-11-02T11:00:00Z' })
      }
      return HttpResponse.json(reading)
    }),
  )
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  await userEvent.click(await screen.findByRole('button', { name: 'refresh' }))
  expect(await screen.findByText('Refreshing NVDA… this can take ~20 seconds.')).toBeInTheDocument()
  expect(await screen.findByText('NVDA updated ✓')).toBeInTheDocument()
})

test('first load shows a placeholder layout', async () => {
  const { delay } = await import('msw')
  server.use(
    http.get('/api/readings/NVDA', async () => {
      await delay(200)
      return HttpResponse.json(reading)
    }),
  )
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  expect(screen.getByRole('status', { name: 'Loading reading' })).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: "What's driving it" })).toBeInTheDocument()
})


test('sources show the top 5 with outlet names, the rest on demand', async () => {
  const userEvent = (await import('@testing-library/user-event')).default
  const many = Array.from({ length: 8 }, (_, i) => ({
    ...reading.sources[0], id: `s${i}`, title: `Story ${i}`, url: `https://e.com/${i}`, outlet: 'Reuters',
  }))
  serve({ sources: many })
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  const sources = (await screen.findByRole('heading', { name: 'Sources' })).closest('section')!
  expect(within(sources).getAllByRole('link')).toHaveLength(5)
  expect(within(sources).getAllByText(/Reuters/).length).toBe(5)
  await userEvent.click(within(sources).getByRole('button', { name: 'Show all 8' }))
  expect(within(sources).getAllByRole('link')).toHaveLength(8)
})

test('chart range buttons switch the visible period', async () => {
  const userEvent = (await import('@testing-library/user-event')).default
  serve({})
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  const oneMonth = await screen.findByRole('button', { name: '1M' })
  expect(screen.getByRole('button', { name: '1Y' })).toHaveAttribute('aria-pressed', 'true')
  await userEvent.click(oneMonth)
  expect(oneMonth).toHaveAttribute('aria-pressed', 'true')
})


test('older readings without a takeaway do not repeat the first driver', async () => {
  serve({ ai: { ...reading.ai!, takeaway: null } })
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  const verdict = await screen.findByRole('region', { name: 'Verdict' })
  expect(within(verdict).queryByText('Data-center guidance raised')).toBeNull()
})

test('chart leaves room on the left so the first date label is not cut off', async () => {
  serve({})
  renderWithClient(<ReadingPanel ticker="NVDA" />)
  await screen.findByRole('button', { name: '1Y' })
  expect(ranges.at(-1)!.from).toBeLessThan(0)
})

test('why it moved is the first card in the main column, above the chart', async () => {
  serve({
    move: { date: '2026-10-30', change_pct: 2.3, typical_pct: 2.5, notable: false },
  })
  const { container } = renderWithClient(<ReadingPanel ticker="NVDA" />)
  expect(await screen.findByText('Why it moved')).toBeInTheDocument()
  const main = container.querySelector('.rail-main')!
  expect(main.firstElementChild).toHaveClass('why-moved')
})
