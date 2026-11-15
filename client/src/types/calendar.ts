/**
 * Types mirroring `GET /api/v1/calendar` (see `server/docs/api.md`).
 *
 * A month missing from `months` means "no data loaded"; a month with
 * `count: 0` means "observed, no fires". Keep that distinction in the UI.
 */

/** Hotspot count of one calendar month in the selected area. */
export type CalendarMonth = {
  year: number
  /** 1 = January … 12 = December. */
  month: number
  count: number
  modis: number
  viirs: number
  /** True when the loaded data covers only part of this month. */
  partial: boolean
}

/** Total of one year; `partial` when any of its months is missing or partial. */
export type CalendarYear = {
  year: number
  count: number
  partial: boolean
}

/** Response of `GET /api/v1/calendar`. */
export type CalendarData = {
  /** `[min_lon, min_lat, max_lon, max_lat]` */
  bbox: [number, number, number, number]
  /** First and last loaded day (UTC), or null when the database is empty. */
  coverage: { start_date: string; end_date: string } | null
  /** False while counts are raw MODIS + VIIRS detections. */
  harmonized: boolean
  total: number
  months: CalendarMonth[]
  years: CalendarYear[]
  /** Index 0 = January. Median over full months only; null when there is none. */
  monthly_median: (number | null)[]
  /** Present only when `total` is 0. */
  message?: string
}
