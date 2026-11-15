import { useMemo } from 'react'
import { useStats } from '../../hooks/useStats'
import { type DistributionRow, type StatsQuery } from '../../types/stats'
import {
  AXIS_STYLE,
  GRID_LAYOUT,
  LEGEND_STYLE,
  SENSOR_COLORS,
  emptyMessageOf,
  sensorsIn,
} from '../../utils/chartTheme'
import ChartCard from './ChartCard'
import EChart from './EChart'

/** Props of {@link DistributionChart}. */
type DistributionChartProps = {
  query: StatsQuery
  number: string
  title: string
  field: 'frp' | 'bright_mir' | 'bright_tir' | 'confidence_raw'
  /** Bins of equal width in log10 space; recommended for FRP (very skewed). */
  log?: boolean
  bins?: number
}

/** Short bin edge: 3 significant digits keeps log-scale edges readable. */
function edge(value: number): string {
  return Number(value.toPrecision(3)).toLocaleString('en-US')
}

/**
 * Charts 6-8 and 17: histogram of one field from `/stats/distribution`.
 *
 * Both sensors share the same bin edges (computed by the API), so their bars
 * sit side by side in each bin. The unit comes from the response metadata.
 * Detections without a value (or <= 0 with log bins) are counted in
 * `metadata.excluded` and mentioned under the chart when there are any.
 */
function DistributionChart({
  query,
  number,
  title,
  field,
  log = false,
  bins = 20,
}: DistributionChartProps) {
  const options = useMemo(
    () => ({ field, bins: String(bins), log: String(log) }),
    [field, bins, log],
  )
  const { response, loading, error } = useStats<DistributionRow[]>(
    'distribution',
    query,
    options,
  )
  const rows = useMemo(() => response?.data ?? [], [response])
  const unit = response?.metadata.units.bin_start ?? ''
  const excluded = Number(response?.metadata.excluded ?? 0)

  const option = useMemo(() => {
    const sensors = sensorsIn(rows)
    const firstSensorRows = rows.filter((row) => row.sensor === sensors[0])
    return {
      grid: GRID_LAYOUT,
      legend: LEGEND_STYLE,
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: {
        type: 'category',
        name: unit,
        nameLocation: 'middle',
        nameGap: 26,
        data: firstSensorRows.map(
          (row) => `${edge(row.bin_start)}–${edge(row.bin_end)}`,
        ),
        ...AXIS_STYLE,
      },
      yAxis: { type: 'value', name: 'detections', ...AXIS_STYLE },
      series: sensors.map((sensor) => ({
        name: sensor,
        type: 'bar',
        barGap: '10%',
        itemStyle: { borderRadius: 0 },
        color: SENSOR_COLORS[sensor],
        data: rows
          .filter((row) => row.sensor === sensor)
          .map((row) => row.count),
      })),
    }
  }, [rows, unit])

  const notes = [
    log ? 'Logarithmic bins.' : 'Equal-width bins.',
    field === 'confidence_raw'
      ? 'MODIS only (VIIRS uses low/nominal/high).'
      : '',
    excluded > 0
      ? `${excluded.toLocaleString('en-US')} detections without a value left out.`
      : '',
  ]

  return (
    <ChartCard
      number={number}
      title={title}
      subtitle={`Detections per range of ${unit}. ${notes.join(' ')}`.trim()}
      loading={loading}
      error={error}
      emptyMessage={emptyMessageOf(response, rows.length === 0)}
    >
      <EChart option={option} />
    </ChartCard>
  )
}

export default DistributionChart
