import { ApiError, AuthRequiredError, CancelError, NetworkError, TimeoutError } from './errors'

const BASE_URL = '/api'
const DEFAULT_TIMEOUT = 30_000

interface RequestOptions {
  method?: string
  body?: unknown
  params?: Record<string, string | number | boolean>
  timeout?: number
  signal?: AbortSignal
}

function buildHeaders(body: unknown): HeadersInit | undefined {
  const headers: Record<string, string> = {}
  const apiToken = import.meta.env.VITE_API_TOKEN
  if (apiToken) headers['Authorization'] = `Bearer ${apiToken}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  return Object.keys(headers).length > 0 ? headers : undefined
}

function buildUrl(path: string, params?: Record<string, string | number | boolean>): URL {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v))
    })
  }
  return url
}

async function parseErrorBody(res: Response): Promise<string> {
  try {
    const body = await res.json()
    return typeof body?.detail === 'string' ? body.detail : ''
  } catch {
    return ''
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, params, timeout = DEFAULT_TIMEOUT, signal: externalSignal } = options

  const url = buildUrl(path, params)

  const controller = new AbortController()
  const timeoutId = timeout > 0 ? setTimeout(() => controller.abort(), timeout) : null

  // Merge external signal with timeout signal
  const signal = controller.signal
  const onExternalAbort = () => controller.abort()
  externalSignal?.addEventListener('abort', onExternalAbort, { once: true })

  try {
    const res = await fetch(url, {
      method,
      headers: buildHeaders(body),
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    })

    if (!res.ok) {
      const detail = await parseErrorBody(res)
      if (res.status === 401) throw new AuthRequiredError(detail)
      throw new ApiError(res.status, detail)
    }

    return res.json()
  } catch (err) {
    if (err instanceof ApiError) throw err

    if (err instanceof DOMException && err.name === 'AbortError') {
      // User-initiated cancel via external signal
      if (externalSignal?.aborted) {
        throw new CancelError(err)
      }
      // Timeout-initiated abort
      throw new TimeoutError(timeout, err)
    }

    // TypeError from fetch typically means network failure
    throw new NetworkError(err)
  } finally {
    if (timeoutId !== null) clearTimeout(timeoutId)
    externalSignal?.removeEventListener('abort', onExternalAbort)
  }
}

export interface ApiClientOptions {
  params?: Record<string, string | number | boolean>
  timeout?: number
  signal?: AbortSignal
}

export const apiClient = {
  get: <T>(path: string, params?: Record<string, string | number | boolean>, timeout?: number, signal?: AbortSignal) =>
    request<T>(path, { params, timeout, signal }),
  put: <T>(path: string, body?: unknown, timeout?: number) =>
    request<T>(path, { method: 'PUT', body, timeout }),
  post: <T>(path: string, body?: unknown, timeout?: number, signal?: AbortSignal) =>
    request<T>(path, { method: 'POST', body, timeout, signal }),
  del: <T>(path: string, timeout?: number) =>
    request<T>(path, { method: 'DELETE', timeout }),
  patch: <T>(path: string, body?: unknown, timeout?: number) =>
    request<T>(path, { method: 'PATCH', body, timeout }),
}

export { ApiError, AuthRequiredError, CancelError, NetworkError, TimeoutError }
