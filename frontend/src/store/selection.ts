import { create } from 'zustand'

export type View = 'reading' | 'track' | 'settings' | 'exposure' | 'compare' | 'buys'

interface SelectionState {
  selected: string | null
  view: View
  trackTicker: string | null
  compare: [string | null, string | null]
  select: (ticker: string) => void
  setView: (view: View) => void
  showTrackRecord: (ticker: string | null) => void
  openCompare: (first?: string) => void
}

export const useSelection = create<SelectionState>((set) => ({
  selected: null,
  view: 'reading',
  trackTicker: null,
  compare: [null, null],
  select: (ticker) => set({ selected: ticker, view: 'reading' }),
  setView: (view) => set({ view }),
  showTrackRecord: (ticker) => set({ view: 'track', trackTicker: ticker }),
  openCompare: (first) =>
    set((s) => ({ view: 'compare', compare: first ? [first, s.compare[1] === first ? null : s.compare[1]] : s.compare })),
}))
