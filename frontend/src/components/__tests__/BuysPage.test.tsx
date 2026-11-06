import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { renderWithClient } from '../../test/utils'
import { BuysPage } from '../BuysPage'

test('empty state explains what logging buys gives you', async () => {
  renderWithClient(<BuysPage />)
  expect(
    await screen.findByText('Log your buys to see your average cost, gains and how they compare with simply buying VOO.'),
  ).toBeInTheDocument()
  expect(
    screen.getByText('Already own some? Log it as one buy at your average price (Gotrade shows it on the position).'),
  ).toBeInTheDocument()
})
