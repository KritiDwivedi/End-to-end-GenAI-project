import { env } from '@/lib/env'
import { getAccessToken } from '@/lib/supabase'

export class ApiError extends Error {
  status: number
  isNetworkError: boolean
  body: unknown

  constructor(message: string, options: { status?: number; isNetworkError?: boolean; body?: unknown } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status ?? 0
    this.isNetworkError = options.isNetworkError ?? false
    this.body = options.body
  }
}

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

async function readBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? ''
  if (response.status === 204) {
    return null
  }
  if (contentType.includes('application/json')) {
    return response.json()
  }
  return response.text()
}

async function request<T>(
  method: HttpMethod,
  path: string,
  body?: unknown,
  init?: RequestInit,
): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('Accept', 'application/json')

  if (body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }

  const token = await getAccessToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  let response: Response
  try {
    response = await fetch(new URL(path, env.apiBaseUrl), {
      ...init,
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (error) {
    throw new ApiError('Network request failed', {
      isNetworkError: true,
      body: error,
    })
  }

  const responseBody = await readBody(response)
  if (!response.ok) {
    const message =
      typeof responseBody === 'object' && responseBody !== null && 'detail' in responseBody
        ? String((responseBody as { detail?: unknown }).detail ?? `HTTP ${response.status}`)
        : `HTTP ${response.status}`

    throw new ApiError(message, {
      status: response.status,
      body: responseBody,
    })
  }

  return responseBody as T
}

export const http = {
  get: <T>(path: string, init?: RequestInit) => request<T>('GET', path, undefined, init),
  post: <T>(path: string, body?: unknown, init?: RequestInit) => request<T>('POST', path, body, init),
  put: <T>(path: string, body?: unknown, init?: RequestInit) => request<T>('PUT', path, body, init),
  patch: <T>(path: string, body?: unknown, init?: RequestInit) => request<T>('PATCH', path, body, init),
  delete: <T>(path: string, body?: unknown, init?: RequestInit) => request<T>('DELETE', path, body, init),
}

