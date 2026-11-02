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

export const handlers = [
  http.get('/api/jobs/morning', () => HttpResponse.json(idleJob)),
  http.get('/api/lists', () => HttpResponse.json(emptyLists)),
  http.get('/api/discover', () =>
    HttpResponse.json({ items: [], created_at: null, spike_scan: null }),
  ),
]
