type Point = { date: string; close: number }
type Holding = { symbol: string; name: string; weight: number }

const ABOUT_A_YEAR = 240 // trading days; less history would mislabel a shorter return

export function oneYearReturn(history: Point[]): number | null {
  if (history.length < ABOUT_A_YEAR) return null
  return (history[history.length - 1].close / history[0].close - 1) * 100
}

/** Rebase a price series to 100 at `from` (inclusive) so two tickers can share one axis. */
export function rebase(history: Point[], from: string): { time: string; value: number }[] {
  const pts = history.filter((p) => p.date >= from)
  if (!pts.length) return []
  const base = pts[0].close
  return pts.map((p) => ({ time: p.date, value: (p.close / base) * 100 }))
}

export function topHoldingsOverlap(a: Holding[], b: Holding[]): { overlap: number; shared: string[] } {
  const bw = new Map(b.map((h) => [h.symbol, h.weight]))
  const shared = a.filter((h) => bw.has(h.symbol))
  return {
    overlap: shared.reduce((sum, h) => sum + Math.min(h.weight, bw.get(h.symbol)!), 0),
    shared: shared.map((h) => h.symbol),
  }
}
