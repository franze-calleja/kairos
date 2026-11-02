import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { useSelection } from '../store/selection'
import { server } from './server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  useSelection.setState({ selected: null, view: 'reading', trackTicker: null, compare: [null, null] })
})
afterAll(() => server.close())
