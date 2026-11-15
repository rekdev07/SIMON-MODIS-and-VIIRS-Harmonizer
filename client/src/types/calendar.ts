/**
 * Types mirroring `GET /api/v1/calendar` (see `server/docs/api.md`).
 *
 * A month missing from `months` means "no data loaded"; a month with
 * `count: 0` means "observed, no fires". Keep that distinction in the UI.
 */

/**
 * What the calendar shows: raw counts of one sensor, or the harmonized series
 * (both sensors combined in MODIS Terra+Aqua units, 2000 → today).
 */
export type CalendarView = 'HARMONIZED' | 'MODIS' | 'VIIRS'

/**
 * Where a harmonized month comes from (see `server/docs/harmonization.md`):
 * - `terra_scaled`: before Aqua (2000 to mid-2002), Terra × factor.
 * - `modis`: Terra + Aqua as counted.
 * - `average`: average of MODIS and VIIRS converted to MODIS units.
 * - `viirs_eq`: VIIRS converted to MODIS units (no MODIS that month).
 */
export type HarmonizedSource = 'terra_scaled' | 'modis' | 'average' | 'viirs_eq'

/** Inclusive UTC date range `YYYY-MM-DD` → `YYYY-MM-DD` (e.g. the dates of the last search). */
export type DateRange = { start: string; end: string }

/** Hotspot count of one calendar month in the selected area. */
export type CalendarMonth = {
  year: number
  /** 1 = January … 12 = December. */
  month: number
  /** Raw count, or the harmonized value (may have decimals) when harmonized. */
  count: number
  modis: number
  viirs: number
  /** True when the loaded data covers only part of this month. */
  partial: boolean
  /** Harmonized calendar only: source of the value. */
  source?: HarmonizedSource
  /** Harmonized calendar only: VIIRS converted to MODIS units, null when unused. */
  modis_eq?: number | null
  terra?: number
  aqua?: number
  viirs_day?: number
  viirs_night?: number
  /** Harmonized calendar only: value below the reliable monthly count. */
  low_count?: boolean
}

/** Fitted parameters and reliability info of a harmonized calendar. */
export type HarmonizationInfo = {
  units: string
  method: string
  r_day: number | null
  r_night: number | null
  r_total: number | null
  terra_factor: number | null
  k_frp: number | null
  /** Monthly count (MODIS units) below which the error grows past ~30 %. */
  min_reliable_count: number
  fit_period: { start_date: string; end_date: string }
  fit_detections: { modis: number; viirs: number }
  terra_fit_period: { start_date: string; end_date: string }
  cutoffs: {
    aqua_start: string
    viirs_start: string
    modis_end: string | null
  }
  reliability: {
    area_deg2: number
    /** Area under ~1° × 1° (≈ 110 km a side): the error grows. */
    small_area: boolean
    small_area_threshold_deg2: number
    /** Mean harmonized value over full months. */
    typical_month: number
    /** `typical_month` below `min_reliable_count`. */
    low_count: boolean
    low_count_months: number
  }
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
  /** False for raw counts of one sensor; true for the harmonized series. */
  harmonized: boolean
  /** Present only when `harmonized` is true. */
  harmonization?: HarmonizationInfo
  total: number
  months: CalendarMonth[]
  years: CalendarYear[]
  /** Index 0 = January. Median over full months only; null when there is none. */
  monthly_median: (number | null)[]
  /** Present only when `total` is 0. */
  message?: string
}
