import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import App from '../../App'
import { renderWithClient } from '../../test/utils'

test('shows the disclaimer and brand', () => {
  renderWithClient(<App />)
  expect(screen.getByText('Kairos is a research tool, not financial advice.')).toBeInTheDocument()
  expect(screen.getByText('KAIROS')).toBeInTheDocument()
})
