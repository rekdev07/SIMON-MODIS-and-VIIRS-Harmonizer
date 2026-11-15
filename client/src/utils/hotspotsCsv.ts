import { type HotspotFeature } from '../types/hotspots'

/**
 * Builds a CSV with one row per hotspot currently shown on the map.
 *
 * GeoJSON stores coordinates as `[longitude, latitude]`; the CSV writes them
 * as separate `latitude,longitude` columns so spreadsheets and GIS tools read
 * them without guessing the order. Null values (`frp`, `confidence`,
 * `fire_type`) become empty fields. All values are numbers or fixed API codes,
 * so no field needs quoting. Each row keeps its `instrument`: raw MODIS and
 * VIIRS detections are listed side by side, never merged.
 */
export function buildHotspotsCsv(features: HotspotFeature[]): string {
  const header =
    'acquired_at,latitude,longitude,instrument,satellite,daynight,frp,confidence,fire_type'
  const lines = features.map(({ geometry, properties: p }) => {
    const [lon, lat] = geometry.coordinates
    return [
      p.acquired_at,
      lat,
      lon,
      p.instrument,
      p.satellite,
      p.daynight,
      p.frp ?? '',
      p.confidence ?? '',
      p.fire_type ?? '',
    ].join(',')
  })
  return [header, ...lines].join('\n') + '\n'
}
