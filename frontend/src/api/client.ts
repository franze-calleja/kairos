import axios, { isAxiosError } from 'axios'
import type { z } from 'zod'

export const api = axios.create({ baseURL: '/api' })

export function apiError(e: unknown): string {
  if (isAxiosError(e)) {
    const detail = (e.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    if (e.response) return `Request failed (${e.response.status})`
    return 'Cannot reach the Kairos server'
  }
  return e instanceof Error ? e.message : 'Something went wrong'
}

export function errorStatus(e: unknown): number | undefined {
  return isAxiosError(e) ? e.response?.status : undefined
}

export async function getParsed<S extends z.ZodType>(
  url: string,
  schema: S,
  params?: Record<string, unknown>,
): Promise<z.infer<S>> {
  const { data } = await api.get(url, { params })
  return schema.parse(data)
}
