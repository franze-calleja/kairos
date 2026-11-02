import { create } from 'zustand'

export type View = 'reading' | 'track' | 'settings' | 'exposure' | 'compare'

interface SelectionState {
  selected: string | null
  view: View
  trackTicker: string | null
  select: (ticker: string) => void
  setView: (view: View) => void
  showTrackRecord: (ticker: string | null) => void
}

export const useSelection = create<SelectionState>((set) => ({
  selected: null,
  view: 'reading',
  trackTicker: null,
  select: (ticker) => set({ selected: ticker, view: 'reading' }),
  setView: (view) => set({ view }),
  showTrackRecord: (ticker) => set({ view: 'track', trackTicker: ticker }),
}))
