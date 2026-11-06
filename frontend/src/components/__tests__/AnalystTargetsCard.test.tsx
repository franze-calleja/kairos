import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { AnalystTargetsCard } from '../reading/AnalystTargetsCard'
import { reading } from '../../test/fixtures/reading'

const withTargets = {
  ...reading.quick,
  target_mean: 245,
  target_median: 240,
  target_low: 180,
  target_high: 300,
  analyst_count: 52,
  analyst_rating: 'Buy',
}

test('shows the analysts target range against today and says whose opinion it is', () => {
  render(<AnalystTargetsCard quick={withTargets} price={204.64} />)
  expect(screen.getByText('$245.00')).toBeInTheDocument()
  expect(screen.getByText('+19.7% vs today')).toBeInTheDocument()
  expect(screen.getByText('$180.00 – $300.00')).toBeInTheDocument()
  expect(screen.getByText(/52 analysts/)).toBeInTheDocument()
  expect(screen.getByText(/Average rating: Buy/)).toBeInTheDocument()
  expect(screen.getByText(/analysts' opinions, not a Kairos forecast/i)).toBeInTheDocument()
})

test('renders nothing without analyst coverage', () => {
  const { container } = render(<AnalystTargetsCard quick={reading.quick} price={204.64} />)
  expect(container).toBeEmptyDOMElement()
})
