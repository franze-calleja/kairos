import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'
import type { Reading } from '../../api/schemas'
import { reading } from '../../test/fixtures/reading'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { ReasonCard } from '../reading/ReasonCard'

const checked: Reading = {
  ...reading,
  thesis_checked: 'AI data-center demand keeps growing',
  ai: {
    ...reading.ai!,
    thesis_check: { verdict: 'challenges', text: 'Export rules may cap China sales', source_ids: ['def'] },
  },
}

test('shows the verdict with a cited explanation', () => {
  renderWithClient(<ReasonCard ticker="NVDA" list="holdings" thesis="AI data-center demand keeps growing" reading={checked} />)
  expect(screen.getByText('Challenges ⚠')).toBeInTheDocument()
  expect(screen.getByText(/Export rules may cap China sales/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '[2]' })).toHaveAttribute('href', 'https://example.com/export')
})

test('an edited reason is marked as not yet checked', () => {
  renderWithClient(<ReasonCard ticker="NVDA" list="holdings" thesis="Something new" reading={checked} />)
  expect(screen.getByText('Refresh to check your updated reason')).toBeInTheDocument()
  expect(screen.queryByText('Challenges ⚠')).toBeNull()
})

test('saving sends the trimmed reason', async () => {
  let body: unknown = null
  server.use(
    http.put('/api/lists/holdings/NVDA/thesis', async ({ request }) => {
      body = await request.json()
      return HttpResponse.json({ ticker: 'NVDA', lean: null, ai_status: null, thesis: 'Moat in CUDA' })
    }),
  )
  renderWithClient(<ReasonCard ticker="NVDA" list="holdings" thesis={null} reading={reading} />)
  await userEvent.type(screen.getByLabelText('Your reason for NVDA'), '  Moat in CUDA  ')
  await userEvent.click(screen.getByRole('button', { name: 'Save reason' }))
  await screen.findByRole('button', { name: 'Save reason' })
  expect(body).toEqual({ thesis: 'Moat in CUDA' })
})

test('tickers not in a list explain how to save a reason', () => {
  renderWithClient(<ReasonCard ticker="PLTR" list={null} thesis={null} reading={reading} />)
  expect(screen.getByText('Add this ticker to a list to save a reason.')).toBeInTheDocument()
})

test('a reason that could not be checked says so instead of asking to refresh', () => {
  const unchecked: Reading = { ...reading, ai: null, ai_status: 'not_enough_signal', thesis_checked: 'AI demand' }
  renderWithClient(<ReasonCard ticker="NVDA" list="holdings" thesis="AI demand" reading={unchecked} />)
  expect(screen.getByText(/Couldn't check your reason this time/)).toBeInTheDocument()
  expect(screen.queryByText('Refresh to check your updated reason')).toBeNull()
})
