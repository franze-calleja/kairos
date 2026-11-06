import { create } from 'zustand'

export type Theme = 'light' | 'dark'
export const THEME_KEY = 'kairos-theme'

/** The theme index.html already applied before first paint (no flash), else light. */
function initial(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme
  try {
    localStorage.setItem(THEME_KEY, theme)
  } catch {
    // private mode or storage disabled: the theme still applies for this visit
  }
}

interface ThemeState {
  theme: Theme
  set: (theme: Theme) => void
  toggle: () => void
}

export const useTheme = create<ThemeState>((setState, get) => ({
  theme: initial(),
  set: (theme) => {
    apply(theme)
    setState({ theme })
  },
  toggle: () => get().set(get().theme === 'dark' ? 'light' : 'dark'),
}))

const CHART_LIGHT = {
  text: '#6b7280',
  grid: '#f3f4f6',
  price: '#4f46e5',
  ma50: '#9ca3af',
  ma200: '#f59e0b',
  pair: ['#4f46e5', '#d97706'], // validated pair on a light surface
} as const
const CHART_DARK = {
  text: '#94a3b8',
  grid: '#273449',
  price: '#818cf8',
  ma50: '#64748b',
  ma200: '#f59e0b',
  pair: ['#818cf8', '#f59e0b'],
} as const

/** Canvas charts can't read CSS variables, so they take their colours from here (stable objects). */
export function chartColors(theme: Theme) {
  return theme === 'dark' ? CHART_DARK : CHART_LIGHT
}
