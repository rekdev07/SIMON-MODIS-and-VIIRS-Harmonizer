import { type ApiErrorBody } from '../types/hotspots'

/**
 * Base URL of the Hotspots API. Read only here so no component hardcodes a host.
 * Override with `VITE_API_BASE_URL` in `.env.local`.
 */
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5000'
).replace(/\/+$/, '')

/**
 * Error thrown by {@link getJson} for API errors and network failures.
 * `message` is ready to show to the user.
 */
export class ApiRequestError extends Error {
  /** API error code (e.g. `INVALID_PARAMETER`) or `NETWORK_ERROR`. */
  readonly code: string
  /** Query parameter that failed validation, when the API reports one. */
  readonly parameter?: string

  constructor(message: string, code: string, parameter?: string) {
    super(message)
    this.name = 'ApiRequestError'
    this.code = code
    this.parameter = parameter
  }
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) {
    return false
  }
  const error = (value as { error: unknown }).error
  return (
    typeof error === 'object' &&
    error !== null &&
    typeof (error as { message?: unknown }).message === 'string'
  )
}

/**
 * GETs `path` with the given query params and parses the JSON body as `T`.
 *
 * Query strings are always built with `URLSearchParams` (never by hand).
 * Non-2xx responses are turned into an {@link ApiRequestError} carrying the
 * API's own message; an unreachable server becomes `NETWORK_ERROR`.
 * Abort errors are re-thrown untouched so callers can ignore them.
 */
export async function getJson<T>(
  path: string,
  params: Record<string, string> = {},
  signal?: AbortSignal,
): Promise<T> {
  const query = new URLSearchParams(params).toString()
  const url = `${API_BASE_URL}${path}${query ? `?${query}` : ''}`

  let response: Response
  try {
    response = await fetch(url, { signal })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiRequestError(
      `Cannot reach the API at ${API_BASE_URL}. Is the server running?`,
      'NETWORK_ERROR',
    )
  }

  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    if (isApiErrorBody(body)) {
      throw new ApiRequestError(
        body.error.message,
        body.error.code,
        body.error.parameter,
      )
    }
    throw new ApiRequestError(
      `Request failed with status ${response.status}`,
      'HTTP_ERROR',
    )
  }
  return body as T
}
