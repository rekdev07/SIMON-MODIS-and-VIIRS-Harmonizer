import { type LatLngPoint } from '../types/hotspots'

/**
 * Parses free text like `"24.02, -104.65"` (latitude first) into a point.
 * Returns null when the text is not two numbers within valid lat/lon ranges.
 */
export function parseLatLng(text: string): LatLngPoint | null {
  const parts = text.split(/[,\s]+/).filter(Boolean)
  if (parts.length !== 2) return null
  const [lat, lng] = parts.map(Number)
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null
  return { lat, lng }
}

/** Formats a point as `"lat, lng"` with a fixed number of decimals. */
export function formatLatLng(point: LatLngPoint, decimals = 4): string {
  return `${point.lat.toFixed(decimals)}, ${point.lng.toFixed(decimals)}`
}

/** Today's date as `YYYY-MM-DD` in UTC (the API's upper date bound). */
export function todayUtc(): string {
  return new Date().toISOString().slice(0, 10)
}
