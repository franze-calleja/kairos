import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'
import { idleJob } from '../../test/handlers'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { RefreshStatus } from '../RefreshStatus'
import { Sidebar } from '../Sidebar'

const running = { ...idleJob, running: true, started_at: '2026-11-02T10:00:00Z' }

test('shows which ticker is being refreshed', async () => {
  server.use(
    http.get('/api/jobs/morning', () =>
      HttpResponse.json({ ...running, phase: 'readings', done: 3, total: 9, current: 'AMZN' }),
    ),
  )
  renderWithClient(<RefreshStatus pollMs={50} />)
  expect(await screen.findByText('Refreshing 4 of 9: AMZN…')).toBeInTheDocument()
})

test('shows Discover scan progress', async () => {
  server.use(
    http.get('/api/jobs/morning', () =>
      HttpResponse.json({ ...running, phase: 'discover', done: 120, total: 503 }),
    ),
  )
  renderWithClient(<RefreshStatus pollMs={50} />)
  expect(await screen.findByText('Scanning S&P 500 for Discover… 120 / 503')).toBeInTheDocument()
})

test('when a run finishes, data reloads by itself and Updated is shown', async () => {
  let polls = 0
  let listFetches = 0
  server.use(
    http.get('/api/jobs/morning', () => {
      polls += 1
      return HttpResponse.json(
        polls === 1 ? { ...running, phase: 'readings', done: 0, total: 2, current: 'NVDA' } : idleJob,
      )
    }),
    http.get('/api/lists', () => {
      listFetches += 1
      return HttpResponse.json({ holdings: [], watching: [] })
    }),
  )
  renderWithClient(
    <>
      <RefreshStatus pollMs={50} />
      <Sidebar />
    </>,
  )
  await waitFor(() => expect(listFetches).toBe(1))
  expect(await screen.findByText(/Updated ✓/)).toBeInTheDocument()
  await waitFor(() => expect(listFetches).toBeGreaterThan(1))
})

test('shows nothing when idle', async () => {
  renderWithClient(<RefreshStatus pollMs={50} />)
  await new Promise((r) => setTimeout(r, 120))
  expect(screen.queryByRole('status')).toBeNull()
})
