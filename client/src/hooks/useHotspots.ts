import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchHotspots, type FetchHotspotsParams } from '../api/hotspots'
import { ApiRequestError } from '../api/client'
import { type HotspotCollection } from '../types/hotspots'

/** Value returned by {@link useHotspots}. */
export type UseHotspotsResult = {
  data: HotspotCollection | null
  loading: boolean
  /** User-facing error message from the API or the network, or null. */
  error: string | null
  /** Runs a new search, aborting any request still in flight. */
  search: (params: Omit<FetchHotspotsParams, 'signal'>) => void
}

/**
 * Loads hotspots on demand. Only the latest search wins: starting a new one
 * aborts the previous request, so a slow old response never overwrites a
 * newer one.
 */
export function useHotspots(): UseHotspotsResult {
  const [data, setData] = useState<HotspotCollection | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)

  useEffect(() => () => controllerRef.current?.abort(), [])

  const search = useCallback((params: Omit<FetchHotspotsParams, 'signal'>) => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller

    setLoading(true)
    setError(null)
    fetchHotspots({ ...params, signal: controller.signal })
      .then((result) => setData(result))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setData(null)
        setError(
          err instanceof ApiRequestError
            ? err.message
            : 'Unexpected error while loading hotspots.',
        )
      })
      .finally(() => {
        if (controllerRef.current === controller) setLoading(false)
      })
  }, [])

  return { data, loading, error, search }
}
