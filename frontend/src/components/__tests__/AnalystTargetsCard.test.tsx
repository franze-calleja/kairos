import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { analystPosition } from '../reading/analyst'
import { AnalystTargetsCard } from '../reading/AnalystTargetsCard'
import { reading } from '../../test/fixtures/reading'

const nvda = {
  ...reading.quick,
  target_mean: 327.14,
  target_median: 315,
  target_low: 180,
  target_high: 515,
  analyst_count: 58,
  analyst_rating: 'Strong buy',
}

test('plain sentence, three boxes and footer', () => {
  render(<AnalystTargetsCard quick={nvda} price={181.6} ticker="NVDA" />)
  expect(screen.getByText('What analysts expect (12 months)')).toBeInTheDocument()
  expect(screen.getByText(/On average,/)).toHaveTextContent(
    "On average, 58 analysts think NVDA will be around $327 in a year. Today it's $181.60.",
  )
  expect(screen.getByText('Lowest')).toBeInTheDocument()
  expect(screen.getByText('$180')).toBeInTheDocument()
  expect(screen.getByText('−1% from today')).toBeInTheDocument()
  expect(screen.getAllByText('$327')).toHaveLength(2) // sentence + average box
  expect(screen.getByText('+80% from today')).toBeInTheDocument()
  expect(screen.getByText('$515')).toBeInTheDocument()
  expect(screen.getByText('+184% from today')).toBeInTheDocument()
  expect(screen.getByText(/right at the lowest guess/)).toBeInTheDocument()
  expect(
    screen.getByText(
      "Average rating: Strong buy · These are analysts' opinions, not a Kairos forecast. Analysts are often too optimistic.",
    ),
  ).toBeInTheDocument()
})

test('analystPosition checks cases in order', () => {
  expect(analystPosition(600, 180, 515)).toBe("Today's price is above every analyst's target, so they think it's run ahead.")
  expect(analystPosition(176, 180, 515)).toBe("Today's price is below every analyst's target.")
  expect(analystPosition(181.6, 180, 515)).toBe(
    "Today's price is right at the lowest guess — even the most cautious analyst expects about the same price.",
  )
  expect(analystPosition(500, 180, 515)).toBe("Today's price is close to the highest guess.")
  expect(analystPosition(300, 180, 515)).toBe("Today's price is between the lowest and highest guesses.")
})

test('without low/high shows the sentence and the average box only', () => {
  render(<AnalystTargetsCard quick={{ ...nvda, target_low: null, target_high: null }} price={181.6} />)
  expect(screen.getByText(/On average,/)).toHaveTextContent('think the stock will be around $327 in a year.')
  expect(screen.getByText('Average')).toBeInTheDocument()
  expect(screen.queryByText('Lowest')).not.toBeInTheDocument()
  expect(screen.queryByText('Highest')).not.toBeInTheDocument()
})

test('renders nothing without analyst coverage', () => {
  const { container } = render(<AnalystTargetsCard quick={reading.quick} price={204.64} />)
  expect(container).toBeEmptyDOMElement()
})
