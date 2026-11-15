import { useStats } from '../../hooks/useStats'
import { type StatsQuery, type SummaryRow } from '../../types/stats'
import {
  SENSOR_COLORS,
  emptyMessageOf,
  formatNumber,
} from '../../utils/chartTheme'
import ChartCard from './ChartCard'

/** Props of {@link KpiCards}. */
type KpiCardsProps = {
  query: StatsQuery
}

/** The five KPIs of chart 1, with their unit. */
const KPIS: {
  key: keyof Omit<SummaryRow, 'sensor'>
  label: string
  unit: string
}[] = [
  { key: 'total_detections', label: 'Detections', unit: '' },
  { key: 'frp_mean', label: 'Mean FRP', unit: 'MW' },
  { key: 'frp_max', label: 'Max FRP', unit: 'MW' },
  { key: 'bright_mir_mean', label: 'Mean MIR brightness', unit: 'K' },
  { key: 'bright_tir_mean', label: 'Mean TIR brightness', unit: 'K' },
]

/**
 * Chart 1: headline numbers per sensor from `/stats/summary`.
 *
 * One row of tiles per sensor, never a combined total: a MODIS detection
 * (~1 km pixel) and a VIIRS detection (~375 m pixel) are not the same unit.
 */
function KpiCards({ query }: KpiCardsProps) {
  const { response, loading, error } = useStats<SummaryRow[]>('summary', query)
  const rows = response?.data ?? []

  return (
    <ChartCard
      number="1"
      title="Key figures"
      subtitle="Per sensor. A detection is a hot satellite pixel, not a fire."
      loading={loading}
      error={error}
      emptyMessage={emptyMessageOf(response, rows.length === 0)}
      wide
    >
      <div className="flex flex-col gap-3">
        {rows.map((row) => (
          <div key={row.sensor} className="flex flex-col gap-2">
            <p className="flex items-center gap-2 text-xs font-semibold text-gray-700">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: SENSOR_COLORS[row.sensor] }}
              />
              {row.sensor}
            </p>
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
              {KPIS.map((kpi) => (
                <div key={kpi.key} className="rounded-lg bg-gray-50 px-3 py-2">
                  <dt className="text-xs text-gray-500">{kpi.label}</dt>
                  <dd className="text-xl font-semibold text-gray-900">
                    {formatNumber(
                      row[kpi.key],
                      kpi.key === 'total_detections' ? 0 : 1,
                    )}
                    {kpi.unit && (
                      <span className="ml-1 text-xs font-normal text-gray-500">
                        {kpi.unit}
                      </span>
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </ChartCard>
  )
}

export default KpiCards
