import { useEffect } from 'react'
import { useMap } from 'react-leaflet'
import { circleMarker, geoJSON } from 'leaflet'
import type { FeatureCollection, Point } from 'geojson'
import {
  type HotspotFeature,
  type HotspotProperties,
} from '../../types/hotspots'
import { frpColor } from '../../utils/frpColor'

/** Props of {@link HotspotLayer}. */
type HotspotLayerProps = {
  features: HotspotFeature[]
}

/** Builds the popup with DOM nodes (textContent) so API strings are never parsed as HTML. */
function buildPopup(p: HotspotProperties): HTMLElement {
  const rows: [string, string][] = [
    ['Acquired', `${p.acquired_at.replace('T', ' ').replace('Z', '')} UTC`],
    ['Instrument', `${p.instrument} (${p.satellite})`],
    ['FRP', p.frp === null ? 'n/a' : `${p.frp.toFixed(2)} MW`],
    ['Confidence', p.confidence ?? 'n/a'],
    ['Day/Night', p.daynight === 'D' ? 'Day' : 'Night'],
  ]
  const root = document.createElement('dl')
  root.className = 'grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs'
  for (const [label, value] of rows) {
    const dt = document.createElement('dt')
    dt.className = 'font-semibold text-gray-600'
    dt.textContent = label
    const dd = document.createElement('dd')
    dd.textContent = value
    root.append(dt, dd)
  }
  return root
}

/**
 * Draws the hotspots as small circles colored by FRP (see `frpColor`).
 *
 * Uses Leaflet's `L.geoJSON` imperatively instead of one React component per
 * point: results can hold up to 50k hotspots, and together with the map's
 * `preferCanvas` this keeps rendering fast. `L.geoJSON` also takes care of
 * the GeoJSON `[longitude, latitude]` to Leaflet `[lat, lng]` swap.
 */
function HotspotLayer({ features }: HotspotLayerProps) {
  const map = useMap()

  useEffect(() => {
    if (features.length === 0) return
    const collection: FeatureCollection<Point, HotspotProperties> = {
      type: 'FeatureCollection',
      features,
    }
    const layer = geoJSON<HotspotProperties, Point>(collection, {
      pointToLayer: (feature, latlng) =>
        circleMarker(latlng, {
          radius: 5,
          color: '#1f2937',
          weight: 0.5,
          fillColor: frpColor(feature.properties.frp),
          fillOpacity: 0.85,
        }),
      onEachFeature: (feature, marker) =>
        marker.bindPopup(() => buildPopup(feature.properties)),
    }).addTo(map)
    return () => {
      layer.remove()
    }
  }, [features, map])

  return null
}

export default HotspotLayer
