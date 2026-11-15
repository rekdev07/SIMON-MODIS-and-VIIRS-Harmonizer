import { useEffect, useState } from 'react'
import { Rectangle, useMap, useMapEvents } from 'react-leaflet'
import { latLngBounds, type LatLng, type LeafletMouseEvent } from 'leaflet'
import { type Bounds } from '../../types/hotspots'

/** Props of {@link RectangleDrawer}. */
type RectangleDrawerProps = {
  /** When true, click-and-drag on the map draws a new rectangle. */
  active: boolean
  /** Currently saved rectangle, always rendered. */
  bounds: Bounds | null
  /** Called with the new corners once the user releases the mouse. */
  onChange: (bounds: Bounds) => void
  /** Called when a drawing gesture ends, so the parent can leave draw mode. */
  onFinish: () => void
}

const SAVED_STYLE = { color: '#2563eb', weight: 2, fillOpacity: 0.08 }
const PREVIEW_STYLE = { ...SAVED_STYLE, dashArray: '6 4' }

/**
 * Lets the user draw a selection rectangle without any extra plugin.
 *
 * While `active`, map dragging is disabled so the mouse gesture draws instead
 * of panning: `mousedown` fixes the first corner, `mousemove` updates a dashed
 * preview, and `mouseup` normalizes both corners with `latLngBounds` into
 * south-west / north-east (what the API expects as `lat1,lon1,lat2,lon2`).
 * A zero-size box (a plain click) is ignored because the API rejects it.
 */
function RectangleDrawer({
  active,
  bounds,
  onChange,
  onFinish,
}: RectangleDrawerProps) {
  const map = useMap()
  const [start, setStart] = useState<LatLng | null>(null)
  const [current, setCurrent] = useState<LatLng | null>(null)

  useEffect(() => {
    if (!active) return
    const container = map.getContainer()
    map.dragging.disable()
    map.boxZoom.disable()
    container.style.cursor = 'crosshair'
    return () => {
      map.dragging.enable()
      map.boxZoom.enable()
      container.style.cursor = ''
    }
  }, [active, map])

  useMapEvents({
    mousedown(e: LeafletMouseEvent) {
      if (!active) return
      setStart(e.latlng)
      setCurrent(e.latlng)
    },
    mousemove(e: LeafletMouseEvent) {
      if (active && start) setCurrent(e.latlng)
    },
    mouseup(e: LeafletMouseEvent) {
      if (!active || !start) return
      const box = latLngBounds(start, e.latlng)
      setStart(null)
      setCurrent(null)
      if (
        box.getSouth() !== box.getNorth() &&
        box.getWest() !== box.getEast()
      ) {
        const sw = box.getSouthWest()
        const ne = box.getNorthEast()
        onChange({
          southWest: { lat: sw.lat, lng: sw.lng },
          northEast: { lat: ne.lat, lng: ne.lng },
        })
      }
      onFinish()
    },
  })

  return (
    <>
      {bounds && !start && (
        <Rectangle
          bounds={[
            [bounds.southWest.lat, bounds.southWest.lng],
            [bounds.northEast.lat, bounds.northEast.lng],
          ]}
          pathOptions={SAVED_STYLE}
          interactive={false}
        />
      )}
      {start && current && (
        <Rectangle
          bounds={latLngBounds(start, current)}
          pathOptions={PREVIEW_STYLE}
          interactive={false}
        />
      )}
    </>
  )
}

export default RectangleDrawer
