import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, errorStatus, getParsed } from './client'
import {
  DiscoverSchema,
  ExposureSchema,
  JobStatusSchema,
  ListEntrySchema,
  ListsSchema,
  ReadingSchema,
  SettingsSchema,
  TrackRecordSchema,
  type ListName,
} from './schemas'

const FIVE_MIN = 5 * 60 * 1000

export const useLists = () =>
  useQuery({ queryKey: ['lists'], queryFn: () => getParsed('/lists', ListsSchema) })

export const useReading = (ticker: string | null) =>
  useQuery({
    queryKey: ['reading', ticker],
    queryFn: () => getParsed(`/readings/${encodeURIComponent(ticker!)}`, ReadingSchema),
    enabled: !!ticker,
    staleTime: FIVE_MIN,
    retry: (count, e) => errorStatus(e) !== 404 && errorStatus(e) !== 422 && count < 1,
  })

export function useRefreshReading() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (ticker: string) =>
      getParsed(`/readings/${encodeURIComponent(ticker)}`, ReadingSchema, { refresh: true }),
    onSuccess: (reading) => {
      qc.setQueryData(['reading', reading.ticker], reading)
      qc.invalidateQueries({ queryKey: ['lists'] })
    },
  })
}

export function useAddTicker() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ list, ticker }: { list: ListName; ticker: string }) =>
      ListEntrySchema.parse((await api.post(`/lists/${list}`, { ticker })).data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lists'] }),
  })
}

export function useRemoveTicker() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ list, ticker }: { list: ListName; ticker: string }) =>
      api.delete(`/lists/${list}/${encodeURIComponent(ticker)}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lists'] }),
  })
}

export const useTrackRecord = (ticker?: string) =>
  useQuery({
    queryKey: ['track-record', ticker ?? null],
    queryFn: () => getParsed('/track-record', TrackRecordSchema, ticker ? { ticker } : undefined),
  })

export const useDiscover = () =>
  useQuery({ queryKey: ['discover'], queryFn: () => getParsed('/discover', DiscoverSchema) })

export const useSettings = () =>
  useQuery({ queryKey: ['settings'], queryFn: () => getParsed('/settings', SettingsSchema) })

export function useRunMorningJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post('/jobs/morning'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] })
      qc.invalidateQueries({ queryKey: ['job-status'] })
    },
  })
}

/** Polls the morning-refresh status: fast while a run is going, slowly otherwise
 * (so a scheduled 07:00 run is noticed if the page was left open). */
export const useJobStatus = (pollMs = { active: 2000, idle: 30_000 }) =>
  useQuery({
    queryKey: ['job-status'],
    queryFn: () => getParsed('/jobs/morning', JobStatusSchema),
    refetchInterval: (query) => (query.state.data?.running ? pollMs.active : pollMs.idle),
    refetchIntervalInBackground: true,
  })

export const useExposure = () =>
  useQuery({ queryKey: ['exposure'], queryFn: () => getParsed('/exposure', ExposureSchema) })

export function useSetShares() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ ticker, shares }: { ticker: string; shares: number | null }) =>
      ListEntrySchema.parse(
        (await api.put(`/lists/holdings/${encodeURIComponent(ticker)}/shares`, { shares })).data,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lists'] })
      qc.invalidateQueries({ queryKey: ['exposure'] })
    },
  })
}
