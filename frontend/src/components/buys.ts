/** Helpers for the My buys page. */

/** Today's date in New York (trade dates are US market days), as YYYY-MM-DD. */
export function nyToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' }).format(now)
}

/** Fractional share counts as Gotrade shows them: 4 decimals. */
export function fmtShares(shares: number): string {
  return shares.toFixed(4)
}

/** "+$12.44" / "−$5.66" */
export function signedUsd(v: number): string {
  const sign = v > 0 ? '+' : v < 0 ? '−' : ''
  return `${sign}$${Math.abs(v).toFixed(2)}`
}
