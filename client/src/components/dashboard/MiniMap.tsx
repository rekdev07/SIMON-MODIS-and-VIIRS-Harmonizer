import { type ReactNode } from 'react'
import { MapContainer, Rectangle, TileLayer } from 'react-leaflet'
import { type Bounds } from '../../types/hotspots'

/** Props of {@link MiniMap}. */
type MiniMapProps = {
  /** Selected area; the map fits it and outlines it. */
  bounds: Bounds
  children: ReactNode
}

/**
 * Small Leaflet map used by the map charts of the dashboard (21, 22).
 *
 * It opens fitted to the selected rectangle. `MapContainer` only reads
 * `bounds` when it mounts, so the parent remounts it (via `key`) when the
 * area changes. `preferCanvas` keeps thousands of markers fast.
 */
function MiniMap({ bounds, children }: MiniMapProps) {
  const leafletBounds: [[number, number], [number, number]] = [
    [bounds.southWest.lat, bounds.southWest.lng],
    [bounds.northEast.lat, bounds.northEast.lng],
  ]
  return (
    <MapContainer
      key={JSON.stringify(leafletBounds)}
      bounds={leafletBounds}
      preferCanvas
      className="h-80 w-full rounded-lg"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Rectangle
        bounds={leafletBounds}
        pathOptions={{ color: '#2563eb', weight: 1.5, fill: false }}
      />
      {children}
    </MapContainer>
  )
}

export default MiniMap
