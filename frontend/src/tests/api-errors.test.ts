import { afterEach, describe, it, expect, vi } from 'vitest'
import { apiClient } from '@/api/client'
import {
  ApiError,
  AuthRequiredError,
  NetworkError,
  TimeoutError,
} from '@/api/errors'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('apiClient error responses', () => {
  it('preserves structured detail objects for readable validation errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        code: 'artist_language_validation_error',
        message: '多语言至少需要两个不同的艺人级演唱主张',
      },
    }), {
      status: 422,
      headers: { 'Content-Type': 'application/json' },
    })))

    await expect(apiClient.get('/structured-error')).rejects.toMatchObject({
      status: 422,
      detail: JSON.stringify({
        code: 'artist_language_validation_error',
        message: '多语言至少需要两个不同的艺人级演唱主张',
      }),
    })
  })
})

describe('ApiError', () => {
  it('has correct name and status', () => {
    const err = new ApiError(500, 'Internal error')
    expect(err.name).toBe('ApiError')
    expect(err.status).toBe(500)
    expect(err.detail).toBe('Internal error')
    expect(err.message).toContain('500')
    expect(err.message).toContain('Internal error')
  })

  it('isAuthError returns true for 401', () => {
    expect(new ApiError(401, '').isAuthError).toBe(true)
    expect(new ApiError(403, '').isAuthError).toBe(false)
  })

  it('isNotFound returns true for 404', () => {
    expect(new ApiError(404, '').isNotFound).toBe(true)
    expect(new ApiError(400, '').isNotFound).toBe(false)
  })

  it('isServerError returns true for 5xx', () => {
    expect(new ApiError(500, '').isServerError).toBe(true)
    expect(new ApiError(400, '').isServerError).toBe(false)
  })

  it('extends Error', () => {
    const err = new ApiError(422, 'Validation failed')
    expect(err).toBeInstanceOf(Error)
    expect(err).toBeInstanceOf(ApiError)
  })
})

describe('AuthRequiredError', () => {
  it('has status 401', () => {
    const err = new AuthRequiredError()
    expect(err.status).toBe(401)
    expect(err.name).toBe('AuthRequiredError')
    expect(err.isAuthError).toBe(true)
  })

  it('accepts custom detail', () => {
    const err = new AuthRequiredError('Token expired')
    expect(err.detail).toBe('Token expired')
  })
})

describe('NetworkError', () => {
  it('has status 0', () => {
    const err = new NetworkError()
    expect(err.status).toBe(0)
    expect(err.name).toBe('NetworkError')
  })
})

describe('TimeoutError', () => {
  it('has status 408 and timeout in message', () => {
    const err = new TimeoutError(30000)
    expect(err.status).toBe(408)
    expect(err.name).toBe('TimeoutError')
    expect(err.message).toContain('30000')
  })
})
