import { useStats } from '../../hooks/useStats'
import { type StatsQuery, type TopEventRow } from '../../types/stats'
import {
  SENSOR_COLORS,
  emptyMessageOf,
  formatNumber,
} from '../../utils/chartTheme'
import ChartCard from './ChartCard'

/** Props of {@link TopEventsTable}. */
type TopEventsTableProps = {
  query: StatsQuery
}

/**
 * Chart 20: the ten detections with the highest FRP, from `/stats/top-events`.
 * Times are shown in UTC exactly as the API sends them (no local conversion).
 */
function TopEventsTable({ query }: TopEventsTableProps) {
  const { response, loading, error } = useStats<TopEventRow[]>(
    'top-events',
    query,
  )
  const rows = response?.data ?? []

  return (
    <ChartCard
      number="20"
      title="Top events by FRP"
      subtitle="The 10 most intense detections. Times in UTC."
      loading={loading}
      error={error}
      emptyMessage={emptyMessageOf(response, rows.length === 0)}
    >
      <div className="max-h-72 overflow-auto">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-white text-gray-500">
            <tr>
              <th className="py-1 pr-2 font-medium">Time (UTC)</th>
              <th className="py-1 pr-2 font-medium">Lat, Lon</th>
              <th className="py-1 pr-2 text-right font-medium">FRP (MW)</th>
              <th className="py-1 pr-2 text-right font-medium">MIR (K)</th>
              <th className="py-1 pr-2 text-right font-medium">TIR (K)</th>
              <th className="py-1 font-medium">Satellite</th>
            </tr>
          </thead>
          <tbody className="text-gray-800">
            {rows.map((row) => (
              <tr
                key={`${row.timestamp_utc}-${row.lat}-${row.lon}-${row.satellite}`}
                className="border-t border-gray-100"
              >
                <td className="py-1 pr-2 whitespace-nowrap">
                  {row.timestamp_utc.replace('T', ' ').replace(':00Z', '')}
                </td>
                <td className="py-1 pr-2 whitespace-nowrap">
                  {row.lat.toFixed(3)}, {row.lon.toFixed(3)}
                </td>
                <td className="py-1 pr-2 text-right font-semibold">
                  {formatNumber(row.frp)}
                </td>
                <td className="py-1 pr-2 text-right">
                  {formatNumber(row.bright_mir)}
                </td>
                <td className="py-1 pr-2 text-right">
                  {formatNumber(row.bright_tir)}
                </td>
                <td className="py-1 whitespace-nowrap">
                  <span
                    className="mr-1.5 inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: SENSOR_COLORS[row.sensor] }}
                  />
                  {row.satellite} ({row.sensor})
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ChartCard>
  )
}

export default TopEventsTable
