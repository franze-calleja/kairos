import { http, HttpResponse } from 'msw'

export const emptyLists = { holdings: [], watching: [] }

export const handlers = [
  http.get('/api/lists', () => HttpResponse.json(emptyLists)),
  http.get('/api/discover', () =>
    HttpResponse.json({ items: [], created_at: null, spike_scan: null }),
  ),
]
