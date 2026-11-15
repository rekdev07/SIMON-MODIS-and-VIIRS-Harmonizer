import { type StatsQuery, type StatsResponse } from '../types/stats'
import { getJson } from './client'

/** Names of the dashboard statistics endpoints (`/api/v1/stats/<name>`). */
export type StatsEndpoint =
  | 'summary'
  | 'timeseries'
  | 'distribution'
  | 'scatter'
  | 'calendar'
  | 'by-hour'
  | 'by-category'
  | 'by-scan'
  | 'top-events'
  | 'points'
  | 'grid'
  | 'sensor-comparison'
  | 'monthly'
  | 'celldays'

/**
 * Builds the query parameters shared by every stats endpoint.
 *
 * Corners go out as south-west = `lat1,lon1` and north-east = `lat2,lon2`
 * (the API accepts any order). Filters left empty are not sent, so the API
 * applies its own defaults. Endpoint options (`freq`, `bins`...) are merged
 * last so they can override a filter, e.g. `fire_type=all` for the type chart.
 */
export function buildStatsParams(
  query: StatsQuery,
  options: Record<string, string> = {},
): Record<string, string> {
  const params: Record<string, string> = {
    lat1: String(query.bounds.southWest.lat),
    lon1: String(query.bounds.southWest.lng),
    lat2: String(query.bounds.northEast.lat),
    lon2: String(query.bounds.northEast.lng),
    start_date: query.startDate,
    end_date: query.endDate,
  }
  for (const [key, value] of Object.entries(query.filters)) {
    if (value !== '') params[key] = value
  }
  return { ...params, ...options }
}

/**
 * Fetches one stats endpoint. The query string is built with
 * `URLSearchParams` inside {@link getJson}; errors become `ApiRequestError`.
 */
export function fetchStats<T>(
  endpoint: StatsEndpoint,
  query: StatsQuery,
  options: Record<string, string> = {},
  signal?: AbortSignal,
): Promise<StatsResponse<T>> {
  return getJson<StatsResponse<T>>(
    `/api/v1/stats/${endpoint}`,
    buildStatsParams(query, options),
    signal,
  )
}
