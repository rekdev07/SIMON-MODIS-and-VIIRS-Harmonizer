import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchCalendar } from '../api/calendar'
import { ApiRequestError } from '../api/client'
import { type CalendarData } from '../types/calendar'
import { type Bounds } from '../types/hotspots'
import { type Sensor } from '../types/stats'

/** Value returned by {@link useCalendar}. */
export type UseCalendarResult = {
  data: CalendarData | null
  loading: boolean
  /** User-facing error message, or null. */
  error: string | null
  /** Loads the calendar of `bounds` for one sensor, aborting any request still in flight. */
  load: (bounds: Bounds, sensor: Sensor) => void
}

/**
 * Loads the burning activity calendar on demand. Like `useHotspots`, only the
 * latest request wins so a slow old response never replaces a newer one.
 */
export function useCalendar(): UseCalendarResult {
  const [data, setData] = useState<CalendarData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)

  useEffect(() => () => controllerRef.current?.abort(), [])

  const load = useCallback((bounds: Bounds, sensor: Sensor) => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller

    setLoading(true)
    setError(null)
    fetchCalendar(bounds, sensor, controller.signal)
      .then((result) => setData(result))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setData(null)
        setError(
          err instanceof ApiRequestError
            ? err.message
            : 'Unexpected error while loading the calendar.',
        )
      })
      .finally(() => {
        if (controllerRef.current === controller) setLoading(false)
      })
  }, [])

  return { data, loading, error, load }
}
