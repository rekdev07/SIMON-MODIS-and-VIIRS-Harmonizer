import { type CalendarData } from '../types/calendar'
import { type Bounds } from '../types/hotspots'
import { type Sensor } from '../types/stats'
import { getJson } from './client'

/**
 * Fetches the burning activity calendar (hotspots per month) of a rectangle.
 *
 * No dates are sent: the API always returns every loaded month so the whole
 * history of the area can be compared. Counting happens in the database, so
 * the response stays small and is never truncated.
 *
 * `instrument` limits the counts to one sensor. The UI always sends it: MODIS
 * and VIIRS counts must not be added together until they are harmonized.
 */
export function fetchCalendar(
  bounds: Bounds,
  instrument: Sensor,
  signal?: AbortSignal,
): Promise<CalendarData> {
  return getJson<CalendarData>(
    '/api/v1/calendar',
    {
      lat1: String(bounds.southWest.lat),
      lon1: String(bounds.southWest.lng),
      lat2: String(bounds.northEast.lat),
      lon2: String(bounds.northEast.lng),
      instrument,
    },
    signal,
  )
}
