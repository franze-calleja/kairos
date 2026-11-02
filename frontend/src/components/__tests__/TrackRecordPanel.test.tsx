import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'
import { server } from '../../test/server'
import { renderWithClient } from '../../test/utils'
import { TrackRecordPanel } from '../TrackRecordPanel'

type Stats = { n: number; avg_change_pct: number | null; avg_excess_pct: number | null; pct_positive: number | null }
const empty: Stats = { n: 0, avg_change_pct: null, avg_excess_pct: null, pct_positive: null }
const h = (s: Stats = empty) => ({ '1': s, '5': s, '20': s })

test('small sample banner and table', async () => {
  server.use(
    http.get('/api/track-record', () =>
      HttpResponse.json({
        by_lean: {
          bullish: h({ n: 2, avg_change_pct: 1.5, avg_excess_pct: 0.4, pct_positive: 100 }),
          neutral: h(),
          bearish: h(),
        },
        small_sample: true,
      }),
    ),
  )
  renderWithClient(<TrackRecordPanel />)
  expect(await screen.findByText("Small sample — don't read much into this yet")).toBeInTheDocument()
  expect(screen.getAllByText('+1.5%').length).toBeGreaterThan(0)
  expect(screen.getAllByText('+0.4%').length).toBeGreaterThan(0)
})
