export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}%`
}

export function ratioPct(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(digits)}%`
}

export function money(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  for (const [unit, size] of [['T', 1e12], ['B', 1e9], ['M', 1e6]] as const) {
    if (Math.abs(value) >= size) return `$${(value / size).toFixed(1)}${unit}`
  }
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

export function num(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

export function daysBetween(fromIso: string, toIso: string): number {
  const from = Date.UTC(...ymd(fromIso))
  const to = Date.UTC(...ymd(toIso))
  return Math.round((to - from) / 86_400_000)
}

function ymd(iso: string): [number, number, number] {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return [y, m - 1, d]
}
