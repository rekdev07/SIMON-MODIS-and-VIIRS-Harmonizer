/**
 * Types mirroring the dashboard statistics API (`/api/v1/stats/*`, see
 * `server/docs/dashboard-api.md`).
 *
 * Every endpoint answers with the same envelope ({@link StatsResponse}): rows
 * in `data`, the applied query in `metadata`, and `message` only when nothing
 * matched. Counts are always per `sensor`: MODIS and VIIRS are never added
 * together because their pixel sizes (1 km vs 375 m) make the counts incomparable.
 */

import { type Bounds } from './hotspots'

/** Sensor (instrument) name used in every stats row. */
export type Sensor = 'MODIS' | 'VIIRS'

/** Optional filters shared by every stats endpoint. Empty string = not applied. */
export type StatsFilters = {
  instrument: '' | Sensor
  satellite: '' | 'Terra' | 'Aqua' | 'SNPP' | 'NOAA-20' | 'NOAA-21'
  daynight: '' | 'D' | 'N'
  confidence_min: 'low' | 'nominal' | 'high'
  /** `0` (default) keeps vegetation and unknown type; `all` disables the filter. */
  fire_type: '0' | '1' | '2' | '3' | 'all'
}

/** Filters applied when the user has not changed anything. */
export const DEFAULT_STATS_FILTERS: StatsFilters = {
  instrument: '',
  satellite: '',
  daynight: '',
  confidence_min: 'low',
  fire_type: '0',
}

/** Area, dates and filters that every chart of the dashboard shares. */
export type StatsQuery = {
  bounds: Bounds
  /** First UTC day, inclusive, `YYYY-MM-DD`. */
  startDate: string
  /** Last UTC day, inclusive, `YYYY-MM-DD`. */
  endDate: string
  filters: StatsFilters
}

/** `metadata` block of every stats response (plus endpoint-specific options). */
export type StatsMetadata = {
  /** `[min_lon, min_lat, max_lon, max_lat]` */
  bbox: [number, number, number, number]
  start_date: string
  end_date: string
  filters: Record<string, string | number | null>
  /** Unit of each numeric field, e.g. `{ "frp_mean": "MW" }`. */
  units: Record<string, string>
  [option: string]: unknown
}

/** Envelope of every `/api/v1/stats/*` response. `message` exists only when empty. */
export type StatsResponse<T> = {
  data: T
  metadata: StatsMetadata
  message?: string
}

/** `/stats/summary` row (chart 1). */
export type SummaryRow = {
  sensor: Sensor
  total_detections: number
  frp_mean: number | null
  frp_max: number | null
  bright_mir_mean: number | null
  bright_tir_mean: number | null
}

/** `/stats/timeseries` row (charts 2-5). `period` is the first day of the period. */
export type TimeseriesRow = {
  period: string
  sensor: Sensor
  detections: number
  frp_total: number | null
  frp_mean: number | null
  bright_mir_mean: number | null
}

/** `/stats/distribution` row (charts 6-8, 17): one histogram bin of one sensor. */
export type DistributionRow = {
  bin_start: number
  bin_end: number
  sensor: Sensor
  count: number
}

/** `/stats/scatter` row (charts 9, 10, 19). */
export type ScatterRow = {
  x: number
  y: number
  sensor: Sensor
  confidence_level: 'low' | 'nominal' | 'high' | null
}

/** `/stats/calendar` row (chart 11). `day_of_year` or `week` depending on granularity. */
export type CalendarRow = {
  year: number
  day_of_year?: number
  week?: number
  date: string
  sensor: Sensor
  value: number | null
}

/** `/stats/by-hour` row (chart 12). */
export type HourRow = {
  hour_utc: number
  sensor: Sensor
  satellite: string
  detections: number
}

/** `/stats/by-category` row (charts 13-16). `null` category = unknown. */
export type CategoryRow = {
  category: string | number | null
  sensor: Sensor
  detections: number
  frp_mean: number | null
}

/** `/stats/by-scan` row (chart 18). */
export type ScanRow = {
  sensor: Sensor
  scan_start: number
  scan_end: number
  detections: number
  frp_p5: number | null
  frp_median: number | null
}

/** `/stats/top-events` row (chart 20). */
export type TopEventRow = {
  /** ISO 8601 UTC with `Z`. */
  timestamp_utc: string
  lat: number
  lon: number
  frp: number
  bright_mir: number | null
  bright_tir: number | null
  sensor: Sensor
  satellite: string
}

/** `/stats/points` row (chart 21). */
export type PointRow = {
  lat: number
  lon: number
  frp: number | null
  sensor: Sensor
}

/** `/stats/grid` row (chart 22). `lat`/`lon` are the cell center. */
export type GridRow = {
  lat: number
  lon: number
  sensor: Sensor
  detections: number
  frp_total: number | null
}

/** `/stats/sensor-comparison` body (charts 23-24). */
export type SensorComparison = {
  daily: {
    date: string
    sensor: Sensor
    detections: number
    frp_total: number | null
  }[]
  /** Only days where both sensors detected something; empty without VIIRS data. */
  ratio: {
    date: string
    modis_detections: number
    viirs_detections: number
    detections_ratio: number
    frp_ratio: number | null
  }[]
}

/** `/stats/monthly` row (chart 25): calendar month 1-12, all years together. */
export type MonthlyRow = {
  month: number
  sensor: Sensor
  detections: number
  years_with_data: number
}
