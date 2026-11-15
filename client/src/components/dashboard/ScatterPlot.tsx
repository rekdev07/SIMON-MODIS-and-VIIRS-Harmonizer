import { useMemo } from 'react'
import { useStats } from '../../hooks/useStats'
import { type ScatterRow, type StatsQuery } from '../../types/stats'
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

/** Human names of the plottable fields. */
const FIELD_LABELS = {
  bright_mir: 'MIR brightness',
  pixel_area_km2: 'Pixel area',
  bright_tir: 'TIR brightness',
  frp: 'FRP',
} as const

/** Props of {@link ScatterPlot}. */
type ScatterPlotProps = {
  query: StatsQuery
  number: string
  title: string
  x: 'bright_mir' | 'pixel_area_km2'
  y: 'bright_tir' | 'frp'
}

/** Points drawn per chart: enough to see the shape, light enough to stay fast. */
const SAMPLE_LIMIT = '2000'

/**
 * Charts 9, 10 and 19: scatter of two fields from `/stats/scatter`.
 *
 * The API returns a stable pseudo-random sample (same request, same points),
 * so the cloud does not reshuffle when the user reloads. The subtitle says how
 * many detections the sample was drawn from.
 */
function ScatterPlot({ query, number, title, x, y }: ScatterPlotProps) {
  const options = useMemo(() => ({ x, y, limit: SAMPLE_LIMIT }), [x, y])
  const { response, loading, error } = useStats<ScatterRow[]>(
    'scatter',
    query,
    options,
  )
  const rows = useMemo(() => response?.data ?? [], [response])
  const xUnit = response?.metadata.units.x ?? ''
  const yUnit = response?.metadata.units.y ?? ''
  const available = Number(response?.metadata.available ?? 0)

  const option = useMemo(
    () => ({
      grid: { ...GRID_LAYOUT, bottom: 44 },
      legend: LEGEND_STYLE,
      tooltip: {
        trigger: 'item',
        formatter: (p: {
          seriesName: string
          value: [number, number, string]
        }) =>
          `${p.seriesName}<br/>${FIELD_LABELS[x]}: ${formatNumber(p.value[0], 2)} ${xUnit}` +
          `<br/>${FIELD_LABELS[y]}: ${formatNumber(p.value[1], 2)} ${yUnit}` +
          `<br/>Confidence: ${p.value[2]}`,
      },
      xAxis: {
        type: 'value',
        scale: true,
        name: `${FIELD_LABELS[x]} (${xUnit})`,
        nameLocation: 'middle',
        nameGap: 26,
        ...AXIS_STYLE,
      },
      yAxis: {
        type: 'value',
        scale: true,
        name: `${FIELD_LABELS[y]} (${yUnit})`,
        ...AXIS_STYLE,
      },
      series: sensorsIn(rows).map((sensor) => ({
        name: sensor,
        type: 'scatter',
        symbolSize: 5,
        itemStyle: { opacity: 0.6 },
        color: SENSOR_COLORS[sensor],
        data: rows
          .filter((row) => row.sensor === sensor)
          .map((row) => [row.x, row.y, row.confidence_level ?? 'unknown']),
      })),
    }),
    [rows, x, y, xUnit, yUnit],
  )

  return (
    <ChartCard
      number={number}
      title={title}
      subtitle={
        response && rows.length > 0
          ? `${rows.length.toLocaleString('en-US')} of ${available.toLocaleString('en-US')} detections (stable sample).`
          : 'Sample of detections.'
      }
      loading={loading}
      error={error}
      emptyMessage={emptyMessageOf(response, rows.length === 0)}
    >
      <EChart option={option} />
    </ChartCard>
  )
}

export default ScatterPlot
