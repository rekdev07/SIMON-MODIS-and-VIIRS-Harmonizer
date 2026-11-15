import { type Sensor } from '../types/stats'

/**
 * Colors and formatting shared by every dashboard chart.
 *
 * Colors follow the entity, never its rank: MODIS is always blue and VIIRS
 * always orange, in every chart, whichever sensors are present. Satellites
 * keep a fixed color each for the same reason. The hues come from a
 * color-blind-checked categorical palette (first slots validated in pairs).
 */
export const SENSOR_COLORS: Record<Sensor, string> = {
  MODIS: '#2a78d6',
  VIIRS: '#eb6834',
}

/** Fixed color per satellite (MODIS: blue/aqua, VIIRS: orange/magenta/violet). */
export const SATELLITE_COLORS: Record<string, string> = {
  Terra: '#2a78d6',
  Aqua: '#1baf7a',
  SNPP: '#eb6834',
  'NOAA-20': '#e87ba4',
  'NOAA-21': '#6250d6',
}

/** Fallback for a satellite code the palette does not know. */
export const UNKNOWN_COLOR = '#9ca3af'

/** Sequential single-hue ramp (light → dark orange) for magnitude: heat maps. */
export const SEQUENTIAL_RAMP = [
  '#fff1e6',
  '#fdd0a2',
  '#fd8d3c',
  '#d94801',
  '#7f2704',
]

/** Recessive ink for axes and grid lines, so data marks stand out. */
export const AXIS_COLOR = '#6b7280'
export const GRID_COLOR = '#e5e7eb'

/** Sensors in display order (MODIS first, as the older instrument). */
export const SENSORS: Sensor[] = ['MODIS', 'VIIRS']

/**
 * Formats a number for display; `null` (no value, e.g. a mean over detections
 * without FRP) becomes an em dash instead of `NaN`.
 */
export function formatNumber(
  value: number | null | undefined,
  maximumFractionDigits = 1,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString('en-US', { maximumFractionDigits })
}

/** Sensors present in some rows, in {@link SENSORS} order. */
export function sensorsIn(rows: { sensor: Sensor }[]): Sensor[] {
  const present = new Set(rows.map((row) => row.sensor))
  return SENSORS.filter((sensor) => present.has(sensor))
}

/** Text shown when a valid query matched nothing (the API sends the same text). */
export const NO_DATA_TEXT = 'No data found in the selected area'

/**
 * Computes the `emptyMessage` of a chart card from a stats response.
 *
 * Returns `''` while there is no response yet (the card shows "Loading…"),
 * the API's own `message` (or {@link NO_DATA_TEXT}) when `isEmpty` is true,
 * and null when there is something to draw.
 */
export function emptyMessageOf(
  response: { message?: string } | null,
  isEmpty: boolean,
): string | null {
  if (!response) return ''
  if (isEmpty) return response.message ?? NO_DATA_TEXT
  return null
}

/** Axis styling shared by every cartesian chart: recessive ink and grid. */
export const AXIS_STYLE = {
  axisLine: { lineStyle: { color: AXIS_COLOR } },
  axisLabel: { color: AXIS_COLOR, fontSize: 11 },
  nameTextStyle: { color: AXIS_COLOR, fontSize: 11 },
  splitLine: { lineStyle: { color: GRID_COLOR } },
}

/** Plot area margins leaving room for axis names and the legend on top. */
export const GRID_LAYOUT = {
  left: 56,
  right: 16,
  top: 36,
  bottom: 40,
  containLabel: false,
}

/** Legend on top, in neutral text color (identity is carried by the swatch). */
export const LEGEND_STYLE = {
  top: 0,
  textStyle: { color: '#374151', fontSize: 11 },
  itemWidth: 14,
  itemHeight: 8,
}
