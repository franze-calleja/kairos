const NEAR = 0.05 // within 5% of the lowest/highest target counts as "at" it

/** Where today's price sits against the analysts' range, in plain words. Checked in order. */
export function analystPosition(price: number, low: number, high: number): string {
  if (price > high) return "Today's price is above every analyst's target, so they think it's run ahead."
  if (price < low) return "Today's price is below every analyst's target."
  if (price <= low * (1 + NEAR))
    return "Today's price is right at the lowest guess — even the most cautious analyst expects about the same price."
  if (price >= high * (1 - NEAR)) return "Today's price is close to the highest guess."
  return "Today's price is between the lowest and highest guesses."
}
