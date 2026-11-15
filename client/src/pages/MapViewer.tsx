import { type FormEvent, Suspense, lazy, useState } from 'react'
import { Download } from 'lucide-react'
import SideBar from '../components/ScreenViewer/SideBar'
import HotspotMap from '../components/ScreenViewer/Map'
import ViewToggle, {
  type MainView,
} from '../components/ScreenViewer/ViewToggle'
import type { DashboardArea } from './Dashboard'
import TextField from '../components/fields/TextField'
import DatePicker from '../components/fields/DatePicker'
import Button from '../components/fields/Button'
import { useGeolocation } from '../hooks/useGeolocation'
import { useHotspots } from '../hooks/useHotspots'
import { useDataset } from '../hooks/useDataset'
import { useCalendar } from '../hooks/useCalendar'
import BurnCalendar from '../components/Calendar/BurnCalendar'
import { type CalendarView, type DateRange } from '../types/calendar'
import { type Bounds, type LatLngPoint } from '../types/hotspots'
import { DEFAULT_STATS_FILTERS, type StatsFilters } from '../types/stats'
import { formatLatLng, parseLatLng, todayUtc } from '../utils/coordinates'
import { buildHotspotsCsv } from '../utils/hotspotsCsv'
import { downloadText } from '../utils/download'

/** First day with satellite data (start of MODIS); the API rejects earlier dates. */
const API_MIN_DATE = '2000-11-01'

// Loaded on first use: the dashboard pulls in the charting library (ECharts),
// so the map view does not pay for it.
const Dashboard = lazy(() => import('./Dashboard'))
const MachineLearning = lazy(() => import('./MachineLearning'))

const GEO_STATUS_TEXT = {
  locating: 'Looking for your location…',
  located: 'Using your current location.',
  fallback: 'Location unavailable, showing Durango center.',
} as const

function MapViewer() {
  const geo = useGeolocation()
  const dataset = useDataset()
  const hotspots = useHotspots()
  const calendar = useCalendar()

  // Null = the user has not typed/applied anything, so follow the geolocation.
  const [coordsText, setCoordsText] = useState<string | null>(null)
  const [manualCenter, setManualCenter] = useState<LatLngPoint | null>(null)
  const [flyRequestId, setFlyRequestId] = useState(0)
  const [coordsError, setCoordsError] = useState<string | null>(null)

  const [bounds, setBounds] = useState<Bounds | null>(null)
  const [drawMode, setDrawMode] = useState(false)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  // Area the calendar was loaded for; clicks on the calendar search this area
  // even if the user has started drawing a new one.
  const [calendarBounds, setCalendarBounds] = useState<Bounds | null>(null)
  // What the calendar shows. Raw MODIS and VIIRS counts are never added
  // together (different pixel sizes); the default is the harmonized series,
  // where the server converts VIIRS to MODIS units so the 2000 → today record
  // is continuous. Raw MODIS or VIIRS can still be picked.
  const [calendarView, setCalendarView] = useState<CalendarView>('HARMONIZED')
  // Dates of the last search (Save or a calendar click), outlined in the calendar.
  const [searchedRange, setSearchedRange] = useState<DateRange | null>(null)
  const [selectedMonth, setSelectedMonth] = useState<{
    year: number
    month: number
  } | null>(null)

  // Main area: map or dashboard. The dashboard uses the area and dates last
  // applied with Save, so editing the form does not refetch 21 charts per keystroke.
  const [view, setView] = useState<MainView>('map')
  const [dashboardArea, setDashboardArea] = useState<DashboardArea | null>(null)
  const [statsFilters, setStatsFilters] = useState<StatsFilters>(
    DEFAULT_STATS_FILTERS,
  )

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
    setDashboardArea({ bounds, startDate, endDate })
    calendar.load(bounds, calendarView)
    setCalendarBounds(bounds)
    setSearchedRange({ start: startDate, end: endDate })
    setSelectedMonth(null)
  }

  /** Reloads the calendar of the same area for another view (harmonized or one sensor). */
  const changeCalendarView = (next: CalendarView) => {
    setCalendarView(next)
    if (calendarBounds) calendar.load(calendarBounds, next)
  }

  // Drawing happens on the map, so starting to draw from the dashboard view
  // switches back to the map first.
  const toggleDrawMode = () => {
    if (!drawMode) setView('map')
    setDrawMode(!drawMode)
  }

  /**
   * Shows one calendar month on the map: sets the date pickers to that month
   * (first to last day, clamped to the loaded data so partial months stay
   * valid), searches the calendar's area and switches to the map tab so the
   * hotspots are visible.
   */
  const selectMonth = (year: number, month: number) => {
    if (!calendarBounds) return
    const mm = String(month).padStart(2, '0')
    const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate()
    const first = `${year}-${mm}-01`
    const last = `${year}-${mm}-${String(lastDay).padStart(2, '0')}`
    // ISO dates compare correctly as strings.
    const start = first < minDate ? minDate : first
    const end = last > maxDate ? maxDate : last
    setStartDate(start)
    setEndDate(end)
    setSelectedMonth({ year, month })
    setSearchedRange({ start, end })
    hotspots.search({ bounds: calendarBounds, startDate: start, endDate: end })
    setView('map')
  }

  const showCalendarPanel =
    calendar.loading || calendar.error !== null || calendar.data !== null

  const data = hotspots.data

  /**
   * Saves the hotspots on the map as CSV, named after the searched rectangle
   * and dates. When the result was truncated the file holds only the
   * returned rows; the side panel already warns about that.
   */
  const downloadHotspots = () => {
    if (!data) return
    const [w, s, e, n] = data.metadata.bbox.map((v) => v.toFixed(2))
    const { start_date, end_date } = data.metadata
    downloadText(
      `hotspots_${start_date}_${end_date}_${s}_${w}_${n}_${e}.csv`,
      buildHotspotsCsv(data.features),
    )
  }

  return (
    <div className="grid h-screen grid-cols-[300px_1fr] bg-gray-300">
      <SideBar>
        <h1 className="mb-3 text-xl font-bold">SIMON</h1>
        <ViewToggle view={view} onChange={setView} />
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
            <Button onClick={goToCoords}>Go</Button>
            <Button onClick={useMyLocation}>Use my location</Button>
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
            <Button onClick={toggleDrawMode}>
              {drawMode ? 'Cancel' : bounds ? 'Redraw area' : 'Draw area'}
            </Button>
            <Button onClick={() => setBounds(null)} disabled={!bounds}>
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
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-gray-700">
                  {data.metadata.returned.toLocaleString()} hotspots found.
                </p>
                <button
                  type="button"
                  onClick={downloadHotspots}
                  className="flex items-center gap-1 rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 transition hover:bg-gray-100"
                >
                  <Download size={14} /> CSV
                </button>
              </div>
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

      {view === 'map' ? (
        <div className="flex h-screen min-w-0 flex-col">
          <div className="min-h-0 flex-1">
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
        </div>
      ) : view === 'calendar' ? (
        <div className="h-screen min-w-0 overflow-y-auto bg-gray-50 p-6">
          {!showCalendarPanel && (
            <p className="text-sm text-gray-600">
              Draw or pick an area in the side panel and press Save to load its
              burning activity calendar.
            </p>
          )}
          {calendar.loading && !calendar.data && (
            <p className="text-sm text-gray-600">Loading calendar…</p>
          )}
          {calendar.error && (
            <p className="text-sm text-red-600">{calendar.error}</p>
          )}
          {calendar.data && (
            <BurnCalendar
              data={calendar.data}
              selected={selectedMonth}
              range={searchedRange}
              onSelectMonth={selectMonth}
              view={calendarView}
              onViewChange={changeCalendarView}
            />
          )}
        </div>
      ) : view === 'ml' ? (
        <Suspense
          fallback={
            <p className="flex h-screen items-center justify-center text-sm text-gray-500">
              Loading machine-learning tools…
            </p>
          }
        >
          <MachineLearning />
        </Suspense>
      ) : (
        <Suspense
          fallback={
            <p className="flex h-screen items-center justify-center text-sm text-gray-500">
              Loading dashboard…
            </p>
          }
        >
          <Dashboard
            area={dashboardArea}
            filters={statsFilters}
            onFiltersChange={setStatsFilters}
          />
        </Suspense>
      )}
    </div>
  )
}

export default MapViewer
