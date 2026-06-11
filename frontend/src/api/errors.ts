export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string, cause?: unknown) {
    super(`API error ${status}${detail ? `: ${detail}` : ''}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    if (cause !== undefined) {
      ;(this as { cause?: unknown }).cause = cause
    }
  }

  get isAuthError(): boolean {
    return this.status === 401
  }

  get isNotFound(): boolean {
    return this.status === 404
  }

  get isServerError(): boolean {
    return this.status >= 500
  }
}

export class NetworkError extends ApiError {
  constructor(cause?: unknown) {
    super(0, 'Network request failed', cause)
    this.name = 'NetworkError'
  }
}

export class AuthRequiredError extends ApiError {
  constructor(detail?: string) {
    super(401, detail || 'Authentication required')
    this.name = 'AuthRequiredError'
  }
}

export class TimeoutError extends ApiError {
  constructor(timeoutMs: number, cause?: unknown) {
    super(408, `Request timed out after ${timeoutMs}ms`, cause)
    this.name = 'TimeoutError'
  }
}

export class CancelError extends Error {
  constructor(cause?: unknown) {
    super('Request cancelled')
    this.name = 'CancelError'
    if (cause !== undefined) {
      ;(this as { cause?: unknown }).cause = cause
    }
  }
}
