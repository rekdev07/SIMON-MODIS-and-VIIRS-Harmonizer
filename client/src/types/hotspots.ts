/**
 * Types mirroring the Hotspots API responses (see `server/docs/api.md`).
 *
 * Coordinate order warning: GeoJSON uses `[longitude, latitude]`, while Leaflet
 * and every `LatLngPoint` in this app use latitude first.
 */

/** A geographic point, latitude first (Leaflet order). */
export type LatLngPoint = {
  lat: number
  lng: number
}

/**
 * Rectangle selected by the user, stored as its two opposite corners.
 * They map directly to the API's `lat1,lon1` (south-west) and `lat2,lon2` (north-east).
 */
export type Bounds = {
  southWest: LatLngPoint
  northEast: LatLngPoint
}

/** Properties of one hotspot feature in the GeoJSON response. */
export type HotspotProperties = {
  /** Acquisition time, ISO-8601 in UTC (ends with `Z`). */
  acquired_at: string
  instrument: 'MODIS' | 'VIIRS'
  satellite: string
  daynight: 'D' | 'N'
  /** Fire Radiative Power in MW; may be null. */
  frp: number | null
  confidence: 'low' | 'nominal' | 'high' | null
  /** 0 vegetation, 1 volcano, 2 static source, 3 offshore; may be null. */
  fire_type: number | null
}

/** One hotspot as a GeoJSON point. `coordinates` is `[longitude, latitude]`. */
export type HotspotFeature = {
  type: 'Feature'
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: HotspotProperties
}

/** Metadata describing the query that produced a hotspot collection. */
export type HotspotMetadata = {
  /** `[min_lon, min_lat, max_lon, max_lat]` */
  bbox: [number, number, number, number]
  start_date: string
  end_date: string
  returned: number
  limit: number
  offset: number
  /** True when more hotspots exist than `limit`; the result is incomplete. */
  truncated: boolean
}

/**
 * Response of `GET /api/v1/hotspots`. An empty result is still HTTP 200 and
 * carries `message` (e.g. "No data found in the selected area").
 */
export type HotspotCollection = {
  type: 'FeatureCollection'
  features: HotspotFeature[]
  metadata: HotspotMetadata
  message?: string
}

/** Response of `GET /api/v1/dataset`: what the loaded database covers. */
export type DatasetInfo = {
  total_records: number
  /** Earliest `acq_date` (`YYYY-MM-DD`) or null when the table is empty. */
  min_date: string | null
  max_date: string | null
  instruments: Record<string, number>
  bbox: [number, number, number, number] | null
}

/** Error body returned by the API for every non-2xx response. */
export type ApiErrorBody = {
  error: {
    code: string
    message: string
    /** Only present for `INVALID_PARAMETER`: the offending query parameter. */
    parameter?: string
  }
}
