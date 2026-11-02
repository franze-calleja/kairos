/** Mirrors the backend's normalize_ticker so query keys match what the API returns. */
export function normalizeTicker(raw: string): string {
  return raw.trim().replace(/^\$+/, '').trim().toUpperCase().replaceAll('.', '-')
}
