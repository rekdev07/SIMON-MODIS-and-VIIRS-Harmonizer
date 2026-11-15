import { useMemo } from 'react'
import { useStats } from '../../hooks/useStats'
import { type ScanRow, type StatsQuery } from '../../types/stats'
import {
  AXIS_STYLE,
  GRID_LAYOUT,
  LEGEND_STYLE,
  SENSOR_COLORS,
  emptyMessageOf,
  formatNumber,
  sensorsIn,
} from '../../utils/chartTheme'
import ChartCard from './ChartCard'
import EChart from './EChart'

/** Props of {@link ScanChart}. */
type ScanChartProps = {
  query: StatsQuery
}

/**
 * Chart 18: view-angle effect from `/stats/by-scan`.
 *
 * Pixels near the edge of the satellite swath are larger (bigger `scan`), so
 * only stronger fires get detected there and FRP rises with scan size. Each
 * scan range is drawn at its midpoint: a solid line for the median FRP and a
 * dashed line for the 5th percentile, per sensor (each sensor has its own
 * ranges because MODIS pixels are ~1-4.8 km and VIIRS ~0.3-0.8 km).
 */
function ScanChart({ query }: ScanChartProps) {
  const { response, loading, error } = useStats<ScanRow[]>('by-scan', query)
  const rows = useMemo(() => response?.data ?? [], [response])

  const option = useMemo(() => {
    const point = (row: ScanRow, value: number | null) => ({
      value: [(row.scan_start + row.scan_end) / 2, value],
      range: `${formatNumber(row.scan_start, 2)}–${formatNumber(row.scan_end, 2)} km`,
      detections: row.detections,
    })
    return {
      grid: { ...GRID_LAYOUT, bottom: 44 },
      legend: LEGEND_STYLE,
      tooltip: {
        trigger: 'item',
        formatter: (p: {
          seriesName: string
          data: {
            value: [number, number | null]
            range: string
            detections: number
          }
        }) =>
          `${p.seriesName}<br/>Scan ${p.data.range}<br/>` +
          `${formatNumber(p.data.value[1])} MW · ${formatNumber(p.data.detections, 0)} detections`,
      },
      xAxis: {
        type: 'value',
        scale: true,
        name: 'Scan size (km)',
        nameLocation: 'middle',
        nameGap: 26,
        ...AXIS_STYLE,
      },
      yAxis: { type: 'value', name: 'FRP (MW)', ...AXIS_STYLE },
      series: sensorsIn(rows).flatMap((sensor) => {
        const own = rows.filter((row) => row.sensor === sensor)
        return [
          {
            name: `${sensor} median`,
            type: 'line',
            symbolSize: 8,
            lineStyle: { width: 2 },
            color: SENSOR_COLORS[sensor],
            data: own.map((row) => point(row, row.frp_median)),
          },
          {
            name: `${sensor} 5th percentile`,
            type: 'line',
            symbolSize: 8,
            lineStyle: { width: 2, type: 'dashed' },
            color: SENSOR_COLORS[sensor],
            data: own.map((row) => point(row, row.frp_p5)),
          },
        ]
      }),
    }
  }, [rows])

  return (
    <ChartCard
      number="18"
      title="View-angle effect"
      subtitle="FRP median (solid) and 5th percentile (dashed) per scan-size range."
      loading={loading}
      error={error}
      emptyMessage={emptyMessageOf(response, rows.length === 0)}
    >
      <EChart option={option} />
    </ChartCard>
  )
}

export default ScanChart
