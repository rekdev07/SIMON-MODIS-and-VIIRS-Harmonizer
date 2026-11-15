/** One step of the FRP color scale: values below `max` get `color`. */
export type FrpStep = {
  /** Exclusive upper bound in MW (`Infinity` for the last step). */
  max: number
  color: string
  label: string
}

/**
 * Stepped color scale for Fire Radiative Power (MW), from weak (yellow) to
 * intense (dark red). Shared by the map markers and the legend so both always agree.
 */
export const FRP_STEPS: FrpStep[] = [
  { max: 5, color: '#fde047', label: '< 5' },
  { max: 15, color: '#fb923c', label: '5 – 15' },
  { max: 50, color: '#ef4444', label: '15 – 50' },
  { max: 100, color: '#b91c1c', label: '50 – 100' },
  { max: Infinity, color: '#7f1d1d', label: '≥ 100' },
]

/** Color used when a hotspot has no FRP value. */
export const FRP_UNKNOWN_COLOR = '#9ca3af'

/** Returns the fill color for a hotspot's FRP (gray when it is null). */
export function frpColor(frp: number | null): string {
  if (frp === null || Number.isNaN(frp)) return FRP_UNKNOWN_COLOR
  return (FRP_STEPS.find((step) => frp < step.max) ?? FRP_STEPS[0]).color
}
