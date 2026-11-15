import { MapContainer, TileLayer } from 'react-leaflet'
import { LocateFixed, SquareDashed, Trash2 } from 'lucide-react'
import {
  type Bounds,
  type HotspotFeature,
  type LatLngPoint,
} from '../../types/hotspots'
import MapFlyTo from './MapFlyTo'
import MapResizeWatcher from './MapResizeWatcher'
import RectangleDrawer from './RectangleDrawer'
import HotspotLayer from './HotspotLayer'
import FrpLegend from './FrpLegend'
import FloatingBar from './FloatingBar'
import FloatingButton from './FloatingButton'

/** Props of {@link Map}. */
type MapProps = {
  /** Where the map should be centered; changes trigger a fly animation. */
  center: LatLngPoint
  /** Bump to re-center on `center` even if it did not change. */
  flyRequestId: number
  bounds: Bounds | null
  onBoundsChange: (bounds: Bounds | null) => void
  drawMode: boolean
  onDrawModeChange: (active: boolean) => void
  onLocate: () => void
  hotspots: HotspotFeature[]
}

/**
 * Interactive Leaflet map of the viewer: OSM tiles, the selection rectangle,
 * the hotspot markers, the FRP legend and a floating toolbar (draw area,
 * clear area, go to my location).
 *
 * The toolbar and legend sit outside `MapContainer` so clicks on them never
 * reach the map (and never start a rectangle).
 */
function Map({
  center,
  flyRequestId,
  bounds,
  onBoundsChange,
  drawMode,
  onDrawModeChange,
  onLocate,
  hotspots,
}: MapProps) {
  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={[center.lat, center.lng]}
        zoom={9}
        preferCanvas
        className="h-full w-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapResizeWatcher />
        <MapFlyTo target={center} requestId={flyRequestId} />
        <HotspotLayer features={hotspots} />
        <RectangleDrawer
          active={drawMode}
          bounds={bounds}
          onChange={onBoundsChange}
          onFinish={() => onDrawModeChange(false)}
        />
      </MapContainer>

      <FloatingBar className="top-3 right-3 z-[1000]">
        <FloatingButton
          title={drawMode ? 'Cancel drawing' : 'Draw area'}
          active={drawMode}
          onClick={() => onDrawModeChange(!drawMode)}
        >
          <SquareDashed size={18} />
        </FloatingButton>
        <FloatingButton
          title="Clear area"
          onClick={() => onBoundsChange(null)}
          disabled={!bounds}
        >
          <Trash2 size={18} />
        </FloatingButton>
        <FloatingButton title="Go to my location" onClick={onLocate}>
          <LocateFixed size={18} />
        </FloatingButton>
      </FloatingBar>

      <FrpLegend />
    </div>
  )
}

export default Map
