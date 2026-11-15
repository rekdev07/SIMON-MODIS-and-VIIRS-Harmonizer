import { useMemo } from 'react'
import { Info, TriangleAlert } from 'lucide-react'
import { useStats } from '../../hooks/useStats'
import { type CellDaysData, type StatsQuery } from '../../types/stats'
import { emptyMessageOf } from '../../utils/chartTheme'
import { cellDaysMeta } from '../../utils/cellDays'
import CellDaysPhases from './CellDaysPhases'
import CellDaysSeriesChart from './CellDaysSeriesChart'
import CellDaysProfileChart from './CellDaysProfileChart'
import CellDaysCalendar from './CellDaysCalendar'

/** Props of {@link CellDaysPanel}. */
type CellDaysPanelProps = {
  query: StatsQuery
}

/** Monthly request shared by the phases, the profile, the calendar and chart 26. */
const MONTHLY = { freq: 'month' }

/**
 * Cell-day harmonization section of the dashboard (`/stats/celldays`).
 *
 * Every value is in VIIRS SNPP-equivalent cell-days (5 km cells with at
 * least one detection per UTC day). The API switches automatically to MODIS
 * on the days without VIIRS data, so the panel only has to say which periods
 * are observed and which are extrapolated: the period list, the two colors of
 * chart 26 and the markers of chart 28.
 *
 * One monthly request feeds the period list, charts 27 and 28 and the
 * monthly view of chart 26; chart 26 asks again only for weeks or years.
 * The disclaimer (from the API) is always on screen, and the pilot-area
 * warning appears when the rectangle is not the Durango one.
 */
function CellDaysPanel({ query }: CellDaysPanelProps) {
  const { response, loading, error } = useStats<CellDaysData>(
    'celldays',
    query,
    MONTHLY,
  )
  const meta = response ? cellDaysMeta(response.metadata) : null
  // The API still sends rows (all null) for an empty area; `message` is the signal.
  const empty = emptyMessageOf(response, !!response?.message)
  const months = useMemo(() => response?.data.months ?? [], [response])
  const profile = useMemo(() => response?.data.profile ?? [], [response])

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <aside className="flex gap-2 rounded border border-gray-300 bg-white p-3 text-xs text-gray-700 lg:col-span-2">
        <Info size={16} className="mt-0.5 shrink-0 text-blue-600" />
        <p>
          <span className="font-semibold">Disclaimer: </span>
          {meta?.disclaimer ??
            'Cell-days are an indirect metric of the average fire activity level in the region.'}{' '}
          Dashboard filters are not applied here.
        </p>
      </aside>
      {meta?.warning && (
        <aside className="flex gap-2 rounded border border-amber-400 bg-amber-50 p-3 text-xs text-amber-900 lg:col-span-2">
          <TriangleAlert size={16} className="mt-0.5 shrink-0" />
          <p>{meta.warning}</p>
        </aside>
      )}
      {response && meta && !response.message && (
        <CellDaysPhases data={response.data} metadata={meta} />
      )}
      <CellDaysSeriesChart
        query={query}
        monthly={response}
        monthlyLoading={loading}
        monthlyError={error}
      />
      <CellDaysProfileChart
        rows={profile}
        loading={loading}
        error={error}
        emptyMessage={empty}
      />
      <CellDaysCalendar
        months={months}
        loading={loading}
        error={error}
        emptyMessage={empty}
      />
    </div>
  )
}

export default CellDaysPanel
