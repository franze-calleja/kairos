import { act, render } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { useTheme } from '../../store/theme'
import { PriceChart } from '../reading/PriceChart'

const options: { layout?: { textColor?: string; background?: { color?: string } } }[] = []
const seriesColors: string[] = []
vi.mock('lightweight-charts', () => ({
  ColorType: { Solid: 'solid' },
  LineSeries: {},
  createChart: (_el: unknown, o: (typeof options)[number]) => {
    options.push(o)
    return {
      addSeries: (_s: unknown, so: { color: string }) => {
        seriesColors.push(so.color)
        return { setData: () => {} }
      },
      timeScale: () => ({ fitContent: () => {}, setVisibleLogicalRange: () => {} }),
      remove: () => {},
    }
  },
}))

const history = Array.from({ length: 30 }, (_, i) => ({ date: `2026-10-${String(i + 1).padStart(2, '0')}`, close: 100 + i }))

test('chart redraws in the current theme colours on a transparent background', () => {
  useTheme.getState().set('light')
  render(<PriceChart history={history} />)
  expect(options.at(-1)?.layout?.textColor).toBe('#6b7280')
  expect(options.at(-1)?.layout?.background?.color).toBe('transparent')
  expect(seriesColors.at(-3)).toBe('#4f46e5')
  act(() => useTheme.getState().set('dark'))
  expect(options.at(-1)?.layout?.textColor).toBe('#94a3b8')
  expect(seriesColors.at(-3)).toBe('#818cf8')
})
