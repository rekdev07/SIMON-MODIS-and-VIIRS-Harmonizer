/**
 * Color scales of the burning activity calendar.
 *
 * Both ramps come from ColorBrewer and are safe for the common forms of color
 * blindness: YlOrRd (sequential, light → dark as fires increase) for counts,
 * and RdBu (diverging, blue below normal → white → red above normal) for
 * anomalies. Cells are binned instead of using a continuous scale because fire
 * counts are very skewed: on a linear scale one extreme month would wash every
 * other cell out to the lightest color.
 */

/** One step of a binned scale. */
export type ScaleStep = {
  /** Exclusive upper bound (`Infinity` for the last step). */
  max: number
  color: string
  /** Text color with enough contrast on `color`. */
  text: string
  label: string
}

/** Fill of a month that was observed but had no hotspots. */
export const ZERO_COLOR = '#f9fafb'

/** Fill of a month whose ratio to the median cannot be computed. */
export const NO_REFERENCE_COLOR = '#e5e7eb'

const COUNT_COLORS = ['#ffffb2', '#fecc5c', '#fd8d3c', '#f03b20', '#bd0026']
const COUNT_TEXT = ['#374151', '#374151', '#1f2937', '#ffffff', '#ffffff']

/** Rounds a threshold to 1, 2 or 5 × a power of ten so legend labels read well. */
function niceNumber(value: number): number {
  if (value <= 1) return 1
  const power = 10 ** Math.floor(Math.log10(value))
  const fraction = value / power
  const nice = fraction < 1.5 ? 1 : fraction < 3.5 ? 2 : fraction < 7.5 ? 5 : 10
  return nice * power
}

/** Formats a count compactly: `950`, `8.1k`, `137k`. */
export function formatCount(value: number): string {
  if (value < 1000) return String(Math.round(value))
  if (value < 10000) return `${(value / 1000).toFixed(1)}k`
  if (value < 1_000_000) return `${Math.round(value / 1000)}k`
  return `${(value / 1_000_000).toFixed(1)}M`
}

/**
 * Builds five count bins for the area's largest monthly count.
 *
 * How: thresholds grow geometrically from 1 to `maxCount`
 * (`maxCount^(1/5)`, `maxCount^(2/5)`, …), rounded to nice numbers. Why: the
 * same calendar must work for a small ranch (tens of hotspots) and for a whole
 * country (hundreds of thousands), so the bins follow the data.
 */
export function buildCountScale(maxCount: number): ScaleStep[] {
  const thresholds: number[] = []
  for (let i = 1; i < COUNT_COLORS.length; i++) {
    const t = niceNumber(Math.max(1, maxCount) ** (i / COUNT_COLORS.length))
    thresholds.push(Math.max(t, (thresholds.at(-1) ?? 0) + 1))
  }
  return COUNT_COLORS.map((color, i) => {
    const low = i === 0 ? 1 : thresholds[i - 1]
    const max = i < thresholds.length ? thresholds[i] : Infinity
    const label =
      max === Infinity
        ? `≥ ${formatCount(low)}`
        : max - 1 === low
          ? formatCount(low)
          : `${formatCount(low)}–${formatCount(max - 1)}`
    return { max, color, text: COUNT_TEXT[i], label }
  })
}

/**
 * Anomaly bins of `count / median` for the same month. 1 means "a normal
 * month"; 2 means twice the usual activity.
 */
export const ANOMALY_SCALE: ScaleStep[] = [
  { max: 0.5, color: '#2166ac', text: '#ffffff', label: '< 0.5×' },
  { max: 0.8, color: '#92c5de', text: '#1f2937', label: '0.5–0.8×' },
  { max: 1.25, color: '#f7f7f7', text: '#1f2937', label: '0.8–1.25× (normal)' },
  { max: 2, color: '#f4a582', text: '#1f2937', label: '1.25–2×' },
  { max: Infinity, color: '#b2182b', text: '#ffffff', label: '≥ 2×' },
]

/** Returns the step of `scale` that `value` falls in. */
export function stepFor(scale: ScaleStep[], value: number): ScaleStep {
  return scale.find((step) => value < step.max) ?? scale[scale.length - 1]
}

/**
 * Ratio of a month's count to the median of that month, or null when it is
 * not meaningful (no median, or a median of 0 where any fire would be ∞×).
 */
export function anomalyRatio(
  count: number,
  median: number | null,
): number | null {
  if (median === null || median === 0) return null
  return count / median
}
