import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { useSelection } from '../../store/selection'
import { renderWithClient } from '../../test/utils'
import { TopBar } from '../TopBar'

test('search normalizes and selects the ticker', async () => {
  renderWithClient(<TopBar />)
  await userEvent.type(screen.getByPlaceholderText('Check any ticker…'), ' nvda {Enter}')
  expect(useSelection.getState().selected).toBe('NVDA')
  expect(useSelection.getState().view).toBe('reading')
})

test('empty search does nothing', async () => {
  renderWithClient(<TopBar />)
  await userEvent.type(screen.getByPlaceholderText('Check any ticker…'), '   {Enter}')
  expect(useSelection.getState().selected).toBeNull()
})

test('search uses the same ticker form as the backend', async () => {
  renderWithClient(<TopBar />)
  const input = screen.getByPlaceholderText('Check any ticker…')
  await userEvent.type(input, ' $nvda {Enter}')
  expect(useSelection.getState().selected).toBe('NVDA')
  await userEvent.type(input, 'brk.b{Enter}')
  expect(useSelection.getState().selected).toBe('BRK-B')
})

test('clicking the logo returns to the overview', async () => {
  useSelection.getState().select('NVDA')
  renderWithClient(<TopBar />)
  await userEvent.click(screen.getByRole('button', { name: 'Kairos home' }))
  expect(useSelection.getState().selected).toBeNull()
})

test('my buys opens the buys view', async () => {
  renderWithClient(<TopBar />)
  await userEvent.click(screen.getByRole('button', { name: 'My buys' }))
  expect(useSelection.getState().view).toBe('buys')
})
