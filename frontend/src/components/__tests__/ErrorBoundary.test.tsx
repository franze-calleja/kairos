import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { ErrorBoundary } from '../ErrorBoundary'

let broken = true
function Flaky() {
  if (broken) throw new Error('chart exploded')
  return <p>chart ok</p>
}

test('a crash shows a fallback instead of a blank page, and Try again recovers', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  render(
    <ErrorBoundary>
      <Flaky />
    </ErrorBoundary>,
  )
  expect(screen.getByText('Something went wrong showing this view.')).toBeInTheDocument()
  expect(screen.getByText('chart exploded')).toBeInTheDocument()
  broken = false
  await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(screen.getByText('chart ok')).toBeInTheDocument()
})
