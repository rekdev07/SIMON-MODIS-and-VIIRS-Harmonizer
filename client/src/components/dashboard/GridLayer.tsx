import { useEffect } from 'react'
import { useMap } from 'react-leaflet'
import { layerGroup, rectangle } from 'leaflet'
import { type GridRow } from '../../types/stats'
import { formatNumber } from '../../utils/chartTheme'

/** Props of {@link GridLayer}. */
type GridLayerProps = {
  cells: GridRow[]
  /** Cell size in degrees; the API returns cell centers. */
  cell: number
  /** Fill color of a cell from its detection count. */
  colorOf: (detections: number) => string
}

/**
 * Draws the `/stats/grid` cells as filled squares.
 *
 * Each row is a cell center, so the square spans `center ± cell / 2` on both
 * axes. Drawn imperatively in one layer group (fast with many cells).
 */
function GridLayer({ cells, cell, colorOf }: GridLayerProps) {
  const map = useMap()

  useEffect(() => {
    const half = cell / 2
    const group = layerGroup(
      cells.map((row) =>
        rectangle(
          [
            [row.lat - half, row.lon - half],
            [row.lat + half, row.lon + half],
          ],
          {
            stroke: false,
            fillColor: colorOf(row.detections),
            fillOpacity: 0.8,
          },
        ).bindTooltip(
          `${formatNumber(row.detections, 0)} detections · ${formatNumber(row.frp_total)} MW total FRP`,
        ),
      ),
    ).addTo(map)
    return () => {
      group.remove()
    }
  }, [cells, cell, colorOf, map])

  return null
}

export default GridLayer
