import { http, HttpResponse } from 'msw'

export const emptyLists = { holdings: [], watching: [] }

export const idleJob = {
  running: false,
  kind: null,
  phase: null,
  done: 0,
  total: 0,
  current: null,
  started_at: null,
  last_run: null,
}

export const emptyExposure = {
  total_value: 0, positions: [], underlying: [], rest_of_funds: 0, sectors: [], missing_prices: [],
}

export const baseSettings = {
  gemini_configured: true, finnhub_configured: true, sec_configured: true, reddit_enabled: false,
  gemini_model: 'gemini-flash-lite-latest', budget: { minute: 0, day: 3, rpm: 5, rpd: 200 },
  morning_refresh_time: '07:00', evening_refresh_time: '21:00', tz: 'Asia/Manila', reading_cache_hours: 4,
  last_morning_run: '2026-11-02T23:04:00Z', last_evening_run: null, thresholds: {},
}

export const handlers = [
  http.get('/api/exposure', () => HttpResponse.json(emptyExposure)),
  http.get('/api/settings', () => HttpResponse.json(baseSettings)),
  http.get('/api/jobs/morning', () => HttpResponse.json(idleJob)),
  http.get('/api/lists', () => HttpResponse.json(emptyLists)),
  http.get('/api/discover', () =>
    HttpResponse.json({ items: [], created_at: null, spike_scan: null }),
  ),
]
