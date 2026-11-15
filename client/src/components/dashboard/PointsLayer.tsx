import { useEffect } from 'react'
import { useMap } from 'react-leaflet'
import { circleMarker, layerGroup } from 'leaflet'
import { type PointRow } from '../../types/stats'
import { SENSOR_COLORS, formatNumber } from '../../utils/chartTheme'

/** Props of {@link PointsLayer}. */
type PointsLayerProps = {
  points: PointRow[]
}

/**
 * Draws the `/stats/points` rows as small circles colored by sensor.
 *
 * Imperative Leaflet (one layer group) instead of one React component per
 * point, like the main map's hotspot layer: thousands of points stay fast on
 * the canvas renderer. Rows are `lat`/`lon` already (no GeoJSON swap needed).
 */
function PointsLayer({ points }: PointsLayerProps) {
  const map = useMap()

  useEffect(() => {
    const group = layerGroup(
      points.map((point) =>
        circleMarker([point.lat, point.lon], {
          radius: 4,
          color: '#ffffff',
          weight: 0.5,
          fillColor: SENSOR_COLORS[point.sensor],
          fillOpacity: 0.8,
        }).bindTooltip(`${point.sensor} · FRP ${formatNumber(point.frp)} MW`),
      ),
    ).addTo(map)
    return () => {
      group.remove()
    }
  }, [points, map])

  return null
}

export default PointsLayer
