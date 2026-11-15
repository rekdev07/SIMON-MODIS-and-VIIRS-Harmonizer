import {
  type Bounds,
  type DatasetInfo,
  type HotspotCollection,
} from '../types/hotspots'
import { getJson } from './client'

/** Maximum hotspots the API returns in a single response (`MAX_LIMIT`). */
export const HOTSPOTS_MAX_LIMIT = 50000

/** Parameters for {@link fetchHotspots}. */
export type FetchHotspotsParams = {
  bounds: Bounds
  /** First day, inclusive, `YYYY-MM-DD` in UTC. */
  startDate: string
  /** Last day, inclusive, `YYYY-MM-DD` in UTC. */
  endDate: string
  signal?: AbortSignal
}

/**
 * Fetches the hotspots inside a rectangle and date range as GeoJSON.
 *
 * The south-west corner becomes `lat1,lon1` and the north-east corner
 * `lat2,lon2` (the API accepts corners in any order). We ask for the maximum
 * page size so one request covers almost every selection; if more exist the
 * response has `metadata.truncated = true`.
 */
export function fetchHotspots({
  bounds,
  startDate,
  endDate,
  signal,
}: FetchHotspotsParams): Promise<HotspotCollection> {
  return getJson<HotspotCollection>(
    '/api/v1/hotspots',
    {
      lat1: String(bounds.southWest.lat),
      lon1: String(bounds.southWest.lng),
      lat2: String(bounds.northEast.lat),
      lon2: String(bounds.northEast.lng),
      start_date: startDate,
      end_date: endDate,
      limit: String(HOTSPOTS_MAX_LIMIT),
    },
    signal,
  )
}

/** Fetches the dataset summary (date range and extent of the loaded data). */
export function fetchDataset(signal?: AbortSignal): Promise<DatasetInfo> {
  return getJson<DatasetInfo>('/api/v1/dataset', {}, signal)
}
