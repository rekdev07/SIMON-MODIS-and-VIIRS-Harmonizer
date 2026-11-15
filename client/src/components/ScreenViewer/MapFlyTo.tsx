import { useEffect } from 'react'
import { useMap } from 'react-leaflet'
import { type LatLngPoint } from '../../types/hotspots'

/** Props of {@link MapFlyTo}. */
type MapFlyToProps = {
  target: LatLngPoint
  /** Bump this to fly again even when `target` did not change (e.g. after panning away). */
  requestId: number
}

/**
 * Moves the map to `target` whenever it or `requestId` changes.
 * `MapContainer`'s `center` prop only applies on mount, so later center
 * changes (geolocation, typed coordinates) need this helper.
 */
function MapFlyTo({ target, requestId }: MapFlyToProps) {
  const map = useMap()
  const { lat, lng } = target

  useEffect(() => {
    map.flyTo([lat, lng], Math.max(map.getZoom(), 9), { duration: 0.8 })
  }, [map, lat, lng, requestId])

  return null
}

export default MapFlyTo
