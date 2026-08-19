import { http, ApiError } from '@/lib/http'

export type HealthResponse = {
  status: string
}

export type CreateThreadPayload = {
  title?: string
}

export type ThreadSummary = {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export type ApiClient = {
  health: () => Promise<HealthResponse>
  createThread: (payload?: CreateThreadPayload) => Promise<ThreadSummary>
  listThreads: () => Promise<ThreadSummary[]>
}

export const api: ApiClient = {
  health: () => http.get<HealthResponse>('/health'),
  createThread: (payload = {}) => http.post<ThreadSummary>('/threads', payload),
  listThreads: () => http.get<ThreadSummary[]>('/threads'),
}

export { ApiError }
