import { type CalendarData } from '../types/calendar'
import { type Bounds } from '../types/hotspots'
import { getJson } from './client'

/**
 * Fetches the burning activity calendar (hotspots per month) of a rectangle.
 *
 * No dates are sent: the API always returns every loaded month so the whole
 * history of the area can be compared. Counting happens in the database, so
 * the response stays small and is never truncated.
 */
export function fetchCalendar(
  bounds: Bounds,
  signal?: AbortSignal,
): Promise<CalendarData> {
  return getJson<CalendarData>(
    '/api/v1/calendar',
    {
      lat1: String(bounds.southWest.lat),
      lon1: String(bounds.southWest.lng),
      lat2: String(bounds.northEast.lat),
      lon2: String(bounds.northEast.lng),
    },
    signal,
  )
}
