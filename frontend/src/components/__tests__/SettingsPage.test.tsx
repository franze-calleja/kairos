import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { SettingsPage } from '../SettingsPage'

const settings = {
  gemini_configured: true,
  finnhub_configured: false,
  sec_configured: false,
  reddit_enabled: false,
  gemini_model: 'gemini-flash-latest',
  budget: { minute: 0, day: 12, rpm: 10, rpd: 200 },
  morning_refresh_time: '07:00',
  evening_refresh_time: '21:00',
  last_evening_run: null,
  last_backup: '2026-11-03T01:00:00Z',
  backup_dir: '/app/backups',
  backup_keep: 14,
  tz: 'Asia/Manila',
  reading_cache_hours: 4,
  last_morning_run: null,
  thresholds: { micro_cap_usd: 300000000 },
}

test('shows configuration and budget, and can run the morning refresh', async () => {
  let posted = false
  server.use(
    http.get('/api/settings', () => HttpResponse.json(settings)),
    http.post('/api/jobs/morning', () => {
      posted = true
      return HttpResponse.json({ status: 'started' }, { status: 202 })
    }),
  )
  renderWithClient(<SettingsPage />)
  expect(await screen.findByText('Gemini ✓')).toBeInTheDocument()
  expect(screen.getByText('Finnhub ✗')).toBeInTheDocument()
  expect(screen.getByText('12 / 200 AI requests today')).toBeInTheDocument()
  expect(screen.getByText(/Evening refresh at 21:00/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Run morning refresh now' }))
  expect(await screen.findByText(/Morning refresh started/)).toBeInTheDocument()
  expect(posted).toBe(true)
})


test('settings show the last backup and can back up now', async () => {
  let posted = false
  server.use(
    http.get('/api/settings', () => HttpResponse.json(settings)),
    http.post('/api/backup', () => {
      posted = true
      return HttpResponse.json({ file: 'kairos-2026-11-03.db' }, { status: 201 })
    }),
  )
  renderWithClient(<SettingsPage />)
  expect(await screen.findByText(/Last backup:/)).toBeInTheDocument()
  expect(screen.getByText(/keeps the last 14/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Back up now' }))
  expect(await screen.findByText('Saved kairos-2026-11-03.db')).toBeInTheDocument()
  expect(posted).toBe(true)
})
