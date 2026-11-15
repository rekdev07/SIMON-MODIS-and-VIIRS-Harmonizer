import { type CalendarData, type CalendarView } from '../types/calendar'
import { type Bounds } from '../types/hotspots'
import { getJson } from './client'

/**
 * Fetches the burning activity calendar (hotspots per month) of a rectangle.
 *
 * No dates are sent: the API always returns every loaded month so the whole
 * history of the area can be compared. Counting happens in the database, so
 * the response stays small and is never truncated.
 *
 * `view` picks what is counted: `MODIS` or `VIIRS` send `instrument` (raw
 * counts of one sensor, never added together because their pixels differ);
 * `HARMONIZED` sends `harmonized=true` and gets one continuous series in
 * MODIS Terra+Aqua units, where VIIRS was converted with fitted ratios.
 */
export function fetchCalendar(
  bounds: Bounds,
  view: CalendarView,
  signal?: AbortSignal,
): Promise<CalendarData> {
  const area = {
    lat1: String(bounds.southWest.lat),
    lon1: String(bounds.southWest.lng),
    lat2: String(bounds.northEast.lat),
    lon2: String(bounds.northEast.lng),
  }
  const params =
    view === 'HARMONIZED'
      ? { ...area, harmonized: 'true' }
      : { ...area, instrument: view }
  return getJson<CalendarData>('/api/v1/calendar', params, signal)
}
