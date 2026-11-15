import {
  type CellDaysMetadata,
  type CellDaysPeriod,
  type StatsMetadata,
} from '../types/stats'
import { SENSOR_COLORS, formatNumber } from './chartTheme'

/**
 * Shared colors, labels and helpers of the cell-day harmonization panel
 * (charts 26-28, `/stats/celldays`).
 *
 * Observed VIIRS values keep the VIIRS orange used everywhere else, and the
 * values extrapolated from MODIS keep the MODIS blue, so the origin of a bar
 * reads the same as in the other charts.
 */
export const CELL_DAYS_COLORS = {
  viirs: SENSOR_COLORS.VIIRS,
  extrapolated: SENSOR_COLORS.MODIS,
} as const

/** Legend names of the two parts of the series. */
export const CELL_DAYS_LABELS = {
  viirs: 'Observed (VIIRS SNPP)',
  extrapolated: 'Extrapolated from MODIS',
} as const

/** Short unit text for axes and tooltips. */
export const CELL_DAYS_UNIT = 'cell-days'

/** Column labels, one per calendar month. */
export const MONTH_LABELS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]

/**
 * Reads the endpoint-specific metadata of a `/stats/celldays` response. The
 * generic envelope types extra keys as `unknown`; this endpoint always sends
 * the fields of {@link CellDaysMetadata}.
 */
export function cellDaysMeta(
  metadata: StatsMetadata,
): StatsMetadata & CellDaysMetadata {
  return metadata as StatsMetadata & CellDaysMetadata
}

/**
 * Tooltip lines of one period: total, observed and extrapolated parts, and
 * how many days came from each satellite. Partial periods are flagged so a
 * low first or last bar is not read as a drop in activity.
 */
export function periodTooltip(period: CellDaysPeriod, title: string): string {
  const lines = [
    `<b>${title}</b>${period.partial ? ' (partial)' : ''}`,
    period.value === null
      ? 'No satellite data'
      : `${formatNumber(period.value)} ${CELL_DAYS_UNIT}`,
  ]
  if (period.viirs > 0 && period.extrapolated > 0) {
    lines.push(
      `VIIRS ${formatNumber(period.viirs)} · MODIS-extrapolated ${formatNumber(period.extrapolated)}`,
    )
  }
  const days = [
    period.days_viirs && `${period.days_viirs} d VIIRS`,
    period.days_aqua && `${period.days_aqua} d Aqua`,
    period.days_terra && `${period.days_terra} d Terra`,
    period.days_missing && `${period.days_missing} d no data`,
  ].filter(Boolean)
  lines.push(days.join(' · '))
  return lines.join('<br/>')
}
