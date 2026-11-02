import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expect, test, vi } from 'vitest'
import type { Reading } from '../../api/schemas'
import { reading } from '../../test/fixtures/reading'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { ReadingPanel } from '../ReadingPanel'

vi.mock('lightweight-charts', () => ({
  createChart: () => ({
    addSeries: () => ({ setData: () => {} }),
    timeScale: () => ({ fitContent: () => {} }),
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
  expect(screen.getByText('Earnings in 5 days')).toBeInTheDocument()
  expect(screen.getByText('Near its long-term average')).toBeInTheDocument()
  expect(screen.getByText('No warning signs')).toBeInTheDocument()
  expect(screen.getByText(/Bullish/)).toBeInTheDocument()
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
  expect(await screen.findByText('Daily AI limit reached. Numbers below are still current.')).toBeInTheDocument()
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
