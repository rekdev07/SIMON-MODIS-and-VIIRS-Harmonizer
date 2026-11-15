import { useEffect, useState } from 'react'
import { fetchStats, type StatsEndpoint } from '../api/stats'
import { ApiRequestError } from '../api/client'
import { type StatsQuery, type StatsResponse } from '../types/stats'

/** Value returned by {@link useStats}. */
export type UseStatsResult<T> = {
  /** Last successful response, or null before the first one. */
  response: StatsResponse<T> | null
  loading: boolean
  /** User-facing error message from the API or the network, or null. */
  error: string | null
}

type State<T> = {
  key: string
  response: StatsResponse<T> | null
  error: string | null
}

/**
 * Loads one `/api/v1/stats/*` endpoint and reloads it whenever the query or
 * the options change.
 *
 * How: query and options are serialized into a `key`; the effect depends on
 * that string, so a new object with the same values does not refetch. Each
 * run aborts the previous request, so a slow old answer never overwrites a
 * newer one. `loading` is derived (the stored result belongs to another key)
 * instead of being set inside the effect. Passing `null` as query loads nothing.
 */
export function useStats<T>(
  endpoint: StatsEndpoint,
  query: StatsQuery | null,
  options: Record<string, string> = {},
): UseStatsResult<T> {
  const key = query ? JSON.stringify([endpoint, query, options]) : ''
  const [state, setState] = useState<State<T>>({
    key: '',
    response: null,
    error: null,
  })

  useEffect(() => {
    if (!key) return
    const [name, q, opts] = JSON.parse(key) as [
      StatsEndpoint,
      StatsQuery,
      Record<string, string>,
    ]
    const controller = new AbortController()
    fetchStats<T>(name, q, opts, controller.signal)
      .then((response) => setState({ key, response, error: null }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setState({
          key,
          response: null,
          error:
            err instanceof ApiRequestError
              ? err.message
              : 'Unexpected error while loading the chart data.',
        })
      })
    return () => controller.abort()
  }, [key])

  const current = state.key === key
  return {
    response: current ? state.response : null,
    loading: key !== '' && !current,
    error: current ? state.error : null,
  }
}
