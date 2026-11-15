import { useMemo } from 'react'
import { useStats } from '../../hooks/useStats'
import { type HourRow, type StatsQuery } from '../../types/stats'
import {
  AXIS_STYLE,
  GRID_LAYOUT,
  LEGEND_STYLE,
  SATELLITE_COLORS,
  UNKNOWN_COLOR,
  emptyMessageOf,
} from '../../utils/chartTheme'
import ChartCard from './ChartCard'
import EChart from './EChart'

/** Props of {@link HourChart}. */
type HourChartProps = {
  query: StatsQuery
}

const HOURS = Array.from({ length: 24 }, (_, hour) => hour)

/**
 * Chart 12: detections per UTC hour, one bar series per satellite, from
 * `/stats/by-hour`.
 *
 * Bars are grouped, not stacked: stacking satellites would visually add
 * MODIS and VIIRS together. Each satellite passes over at roughly fixed local
 * times, which is why detections cluster in a few hours.
 */
function HourChart({ query }: HourChartProps) {
  const { response, loading, error } = useStats<HourRow[]>('by-hour', query)
  const rows = useMemo(() => response?.data ?? [], [response])

  const option = useMemo(() => {
    const satellites = [...new Set(rows.map((row) => row.satellite))]
    return {
      grid: GRID_LAYOUT,
      legend: LEGEND_STYLE,
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: {
        type: 'category',
        name: 'Hour (UTC)',
        nameLocation: 'middle',
        nameGap: 26,
        data: HOURS.map((hour) => String(hour).padStart(2, '0')),
        ...AXIS_STYLE,
      },
      yAxis: { type: 'value', name: 'detections', ...AXIS_STYLE },
      series: satellites.map((satellite) => {
        const byHour = new Map(
          rows
            .filter((row) => row.satellite === satellite)
            .map((row) => [row.hour_utc, row.detections]),
        )
        const sensor = rows.find((row) => row.satellite === satellite)?.sensor
        return {
          name: `${satellite} (${sensor})`,
          type: 'bar',
          itemStyle: { borderRadius: 0 },
          color: SATELLITE_COLORS[satellite] ?? UNKNOWN_COLOR,
          data: HOURS.map((hour) => byHour.get(hour) ?? 0),
        }
      }),
    }
  }, [rows])

  return (
    <ChartCard
      number="12"
      title="Detection hour"
      subtitle="Detections per hour of acquisition (UTC; Mexico City = UTC−6), per satellite."
      loading={loading}
      error={error}
      emptyMessage={emptyMessageOf(response, rows.length === 0)}
    >
      <EChart option={option} />
    </ChartCard>
  )
}

export default HourChart
