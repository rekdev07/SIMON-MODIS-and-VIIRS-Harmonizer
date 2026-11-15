import { useMemo } from 'react'
import { type Bounds } from '../types/hotspots'
import { type StatsFilters, type StatsQuery } from '../types/stats'
import { formatLatLng } from '../utils/coordinates'
import DashboardFilters from '../components/dashboard/DashboardFilters'
import KpiCards from '../components/dashboard/KpiCards'
import TimeSeriesCharts from '../components/dashboard/TimeSeriesCharts'
import DistributionChart from '../components/dashboard/DistributionChart'
import ScatterPlot from '../components/dashboard/ScatterPlot'
import CalendarChart from '../components/dashboard/CalendarChart'
import HourChart from '../components/dashboard/HourChart'
import CategoryChart from '../components/dashboard/CategoryChart'
import ScanChart from '../components/dashboard/ScanChart'
import TopEventsTable from '../components/dashboard/TopEventsTable'
import PointsMap from '../components/dashboard/PointsMap'
import GridMap from '../components/dashboard/GridMap'
import SensorComparisonCharts from '../components/dashboard/SensorComparisonCharts'
import MonthlyChart from '../components/dashboard/MonthlyChart'

/** Area and dates applied with the side panel's Save button. */
export type DashboardArea = {
  bounds: Bounds
  startDate: string
  endDate: string
}

/** Props of {@link Dashboard}. */
type DashboardProps = {
  /** Last saved area and dates, or null before the first Save. */
  area: DashboardArea | null
  filters: StatsFilters
  onFiltersChange: (filters: StatsFilters) => void
}

/**
 * Dashboard view: the 25 charts for the area and dates saved in the side
 * panel, filtered by the bar at the top.
 *
 * Every chart loads its own `/api/v1/stats/*` endpoint through `useStats`, so
 * each shows its own loading, empty and error state and re-fetches only when
 * the area, dates, filters or its own options change. All numbers are
 * computed by the API; the components only draw them.
 */
function Dashboard({ area, filters, onFiltersChange }: DashboardProps) {
  const query = useMemo<StatsQuery | null>(
    () => (area ? { ...area, filters } : null),
    [area, filters],
  )

  return (
    <div className="h-screen overflow-y-auto bg-gray-100 p-6">
      <header className="mb-4 flex flex-col gap-3">
        <div>
          <h2 className="text-lg font-bold text-gray-900">Dashboard</h2>
          {area ? (
            <p className="text-xs text-gray-600">
              Area SW {formatLatLng(area.bounds.southWest, 2)} · NE{' '}
              {formatLatLng(area.bounds.northEast, 2)} · {area.startDate} to{' '}
              {area.endDate} (UTC, both days included). MODIS and VIIRS are
              always shown separately.
            </p>
          ) : null}
        </div>
        {area && (
          <DashboardFilters filters={filters} onChange={onFiltersChange} />
        )}
      </header>

      {query ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <KpiCards query={query} />
          <TimeSeriesCharts query={query} />
          <DistributionChart
            query={query}
            number="6"
            title="FRP distribution"
            field="frp"
            log
          />
          <DistributionChart
            query={query}
            number="7"
            title="MIR brightness distribution"
            field="bright_mir"
          />
          <DistributionChart
            query={query}
            number="8"
            title="TIR brightness distribution"
            field="bright_tir"
          />
          <ScatterPlot
            query={query}
            number="9"
            title="MIR vs TIR brightness"
            x="bright_mir"
            y="bright_tir"
          />
          <ScatterPlot
            query={query}
            number="10"
            title="Pixel area vs FRP"
            x="pixel_area_km2"
            y="frp"
          />
          <ScatterPlot
            query={query}
            number="19"
            title="MIR brightness vs FRP"
            x="bright_mir"
            y="frp"
          />
          <CalendarChart query={query} />
          <HourChart query={query} />
          <CategoryChart
            query={query}
            number="13"
            title="Day vs night"
            field="daynight"
          />
          <CategoryChart
            query={query}
            number="14"
            title="By satellite"
            field="satellite"
          />
          <CategoryChart
            query={query}
            number="15"
            title="By fire type"
            field="type"
          />
          <CategoryChart
            query={query}
            number="16"
            title="By confidence level"
            field="confidence_level"
          />
          <DistributionChart
            query={query}
            number="17"
            title="MODIS confidence distribution"
            field="confidence_raw"
            bins={10}
          />
          <ScanChart query={query} />
          <TopEventsTable query={query} />
          <PointsMap query={query} />
          <GridMap query={query} />
          <SensorComparisonCharts query={query} />
          <MonthlyChart query={query} />
        </div>
      ) : (
        <div className="flex h-96 items-center justify-center rounded-xl bg-white p-8 text-center text-sm text-gray-600 shadow-sm">
          Draw an area on the map, choose the dates and press Save to see the
          charts.
        </div>
      )}
    </div>
  )
}

export default Dashboard
