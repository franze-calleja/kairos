import { expect, test } from 'vitest'
import { chartColors, THEME_KEY, useTheme } from '../theme'

test('toggle switches the page theme and remembers it', () => {
  useTheme.getState().set('light')
  expect(document.documentElement.dataset.theme).toBe('light')
  useTheme.getState().toggle()
  expect(useTheme.getState().theme).toBe('dark')
  expect(document.documentElement.dataset.theme).toBe('dark')
  expect(localStorage.getItem(THEME_KEY)).toBe('dark')
  useTheme.getState().toggle()
  expect(localStorage.getItem(THEME_KEY)).toBe('light')
})

test('chart colours follow the theme', () => {
  expect(chartColors('light')).toMatchObject({ text: '#6b7280', grid: '#f3f4f6', price: '#4f46e5' })
  expect(chartColors('dark')).toMatchObject({ text: '#94a3b8', grid: '#273449', price: '#818cf8' })
  expect(chartColors('dark').pair).toHaveLength(2)
})
