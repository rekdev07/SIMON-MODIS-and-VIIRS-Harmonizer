import { type FormEvent, useState } from 'react'
import SideBar from '../components/ScreenViewer/SideBar'
import HotspotMap from '../components/ScreenViewer/Map'
import TextField from '../components/fields/TextField'
import DatePicker from '../components/fields/DatePicker'
import Button from '../components/landing/Buttons'
import { useGeolocation } from '../hooks/useGeolocation'
import { useHotspots } from '../hooks/useHotspots'
import { useDataset } from '../hooks/useDataset'
import { type Bounds, type LatLngPoint } from '../types/hotspots'
import { formatLatLng, parseLatLng, todayUtc } from '../utils/coordinates'

/** First day with satellite data (start of MODIS); the API rejects earlier dates. */
const API_MIN_DATE = '2000-11-01'

const GEO_STATUS_TEXT = {
  locating: 'Looking for your location…',
  located: 'Using your current location.',
  fallback: 'Location unavailable, showing Durango center.',
} as const

/**
 * Map viewer page: the sidebar form (place → area → dates) and the map.
 *
 * Flow:
 * 1. Place: starts on the browser location, or Durango's center if it is
 *    unavailable. The user can type `lat, lon` and press Go.
 * 2. Area: the user draws a rectangle; its south-west / north-east corners
 *    are kept in `bounds`.
 * 3. Dates: inclusive UTC days, limited to what the loaded dataset covers.
 *
 * Save stays disabled until every input is filled and valid, then it fetches
 * the hotspots, which the map draws colored by FRP.
 */
function MapViewer() {
  const geo = useGeolocation()
  const dataset = useDataset()
  const hotspots = useHotspots()

  // Null = the user has not typed/applied anything, so follow the geolocation.
  const [coordsText, setCoordsText] = useState<string | null>(null)
  const [manualCenter, setManualCenter] = useState<LatLngPoint | null>(null)
  const [flyRequestId, setFlyRequestId] = useState(0)
  const [coordsError, setCoordsError] = useState<string | null>(null)

  const [bounds, setBounds] = useState<Bounds | null>(null)
  const [drawMode, setDrawMode] = useState(false)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const center = manualCenter ?? geo.position
  const coordsValue = coordsText ?? formatLatLng(geo.position)
  const parsedCoords = parseLatLng(coordsValue)

  const minDate = dataset?.min_date ?? API_MIN_DATE
  const maxDate = dataset?.max_date ?? todayUtc()

  const canSave =
    parsedCoords !== null &&
    bounds !== null &&
    startDate !== '' &&
    endDate !== '' &&
    startDate <= endDate &&
    !hotspots.loading

  const handleCoordsChange = (value: string) => {
    setCoordsText(value)
    setCoordsError(null)
  }

  const goToCoords = () => {
    if (!parsedCoords) {
      setCoordsError('Use "latitude, longitude", e.g. 24.02, -104.65')
      return
    }
    setManualCenter(parsedCoords)
    setFlyRequestId((id) => id + 1)
  }

  const useMyLocation = () => {
    setCoordsText(null)
    setCoordsError(null)
    setManualCenter(null)
    setFlyRequestId((id) => id + 1)
    geo.request()
  }

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!canSave || !bounds) return
    hotspots.search({ bounds, startDate, endDate })
  }

  const data = hotspots.data

  return (
    <div className="grid h-screen grid-cols-[300px_1fr] bg-gray-300">
      <SideBar>
        <h1 className="mb-6 text-xl font-bold">SIMON</h1>
        <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
          <p>Step 1. Choose a place</p>
          <TextField
            label="Coordinates"
            name="coordinates"
            value={coordsValue}
            onChange={handleCoordsChange}
            placeholder="E.g. Latitude, Longitude"
            required
          />
          {coordsError && (
            <p className="-mt-3 text-xs text-red-600">{coordsError}</p>
          )}
          <div className="flex gap-2">
            <Button variant="secondary" onClick={goToCoords}>
              Go
            </Button>
            <Button variant="secondary" onClick={useMyLocation}>
              Use my location
            </Button>
          </div>
          <p className="-mt-3 text-xs text-gray-500">
            {GEO_STATUS_TEXT[geo.status]}
          </p>

          <p>Step 2. Draw the desired area</p>
          {bounds ? (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 text-xs text-gray-700">
              <dt className="font-semibold">SW</dt>
              <dd>{formatLatLng(bounds.southWest)}</dd>
              <dt className="font-semibold">NE</dt>
              <dd>{formatLatLng(bounds.northEast)}</dd>
            </dl>
          ) : (
            <p className="text-xs text-gray-500">
              {drawMode
                ? 'Click and drag on the map to draw the rectangle.'
                : 'No area selected yet.'}
            </p>
          )}
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setDrawMode(!drawMode)}>
              {drawMode ? 'Cancel' : bounds ? 'Redraw area' : 'Draw area'}
            </Button>
            <Button
              variant="secondary"
              onClick={() => setBounds(null)}
              disabled={!bounds}
            >
              Clear
            </Button>
          </div>

          <p>Step 3. Enter the date range to display</p>
          <DatePicker
            label="Start"
            name="start_date"
            value={startDate}
            onChange={setStartDate}
            min={minDate}
            max={endDate || maxDate}
            required
          />
          <DatePicker
            label="End"
            name="end_date"
            value={endDate}
            onChange={setEndDate}
            min={startDate || minDate}
            max={maxDate}
            required
          />
          {startDate && endDate && startDate > endDate && (
            <p className="-mt-3 text-xs text-red-600">
              End date must be on or after the start date.
            </p>
          )}

          <Button type="submit" disabled={!canSave}>
            {hotspots.loading ? 'Loading…' : 'Save'}
          </Button>

          <div className="text-sm" aria-live="polite">
            {hotspots.error && <p className="text-red-600">{hotspots.error}</p>}
            {data && data.message && (
              <p className="text-gray-600">{data.message}</p>
            )}
            {data && data.features.length > 0 && (
              <p className="text-gray-700">
                {data.metadata.returned.toLocaleString()} hotspots found.
              </p>
            )}
            {data?.metadata.truncated && (
              <p className="mt-1 text-amber-700">
                Showing only the first {data.metadata.limit.toLocaleString()}{' '}
                hotspots. Narrow the area or the dates to see all of them.
              </p>
            )}
          </div>
        </form>
      </SideBar>

      <HotspotMap
        center={center}
        flyRequestId={flyRequestId}
        bounds={bounds}
        onBoundsChange={setBounds}
        drawMode={drawMode}
        onDrawModeChange={setDrawMode}
        onLocate={useMyLocation}
        hotspots={data?.features ?? []}
      />
    </div>
  )
}

export default MapViewer
