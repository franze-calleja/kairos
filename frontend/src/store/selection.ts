import { create } from 'zustand'

export type View = 'reading' | 'track' | 'settings'

interface SelectionState {
  selected: string | null
  view: View
  select: (ticker: string) => void
  setView: (view: View) => void
}

export const useSelection = create<SelectionState>((set) => ({
  selected: null,
  view: 'reading',
  select: (ticker) => set({ selected: ticker, view: 'reading' }),
  setView: (view) => set({ view }),
}))
