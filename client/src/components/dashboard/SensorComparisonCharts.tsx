import { useMemo } from 'react'
import { useStats } from '../../hooks/useStats'
import { type SensorComparison, type StatsQuery } from '../../types/stats'
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

/** Props of {@link SensorComparisonCharts}. */
type SensorComparisonChartsProps = {
  query: StatsQuery
}

/** Color of the ratio line: neutral, since it belongs to neither sensor. */
const RATIO_COLOR = '#374151'

/**
 * Charts 23-24: MODIS vs VIIRS from one `/stats/sensor-comparison` request.
 *
 * 23 draws daily detections per sensor side by side. 24 draws the daily
 * VIIRS/MODIS detection ratio, which only exists on days when both sensors
 * detected something; with single-sensor data (e.g. a MODIS-only archive)
 * chart 24 explains why it is empty instead of showing a blank plot.
 */
function SensorComparisonCharts({ query }: SensorComparisonChartsProps) {
  const { response, loading, error } = useStats<SensorComparison>(
    'sensor-comparison',
    query,
  )
  const daily = useMemo(() => response?.data.daily ?? [], [response])
  const ratio = useMemo(() => response?.data.ratio ?? [], [response])

  const dailyOption = useMemo(
    () => ({
      grid: GRID_LAYOUT,
      legend: LEGEND_STYLE,
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value: number) =>
          `${formatNumber(value, 0)} detections`,
      },
      xAxis: { type: 'time', ...AXIS_STYLE, splitLine: { show: false } },
      yAxis: { type: 'value', name: 'detections', ...AXIS_STYLE },
      series: sensorsIn(daily).map((sensor) => ({
        name: sensor,
        type: 'line',
        showSymbol: false,
        lineStyle: { width: 2 },
        color: SENSOR_COLORS[sensor],
        data: daily
          .filter((row) => row.sensor === sensor)
          .map((row) => [row.date, row.detections]),
      })),
    }),
    [daily],
  )

  const ratioOption = useMemo(
    () => ({
      grid: GRID_LAYOUT,
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value: number) => `${formatNumber(value, 2)} × MODIS`,
      },
      xAxis: { type: 'time', ...AXIS_STYLE, splitLine: { show: false } },
      yAxis: { type: 'value', name: 'VIIRS / MODIS', ...AXIS_STYLE },
      series: [
        {
          name: 'Detection ratio',
          type: 'line',
          symbolSize: 6,
          lineStyle: { width: 2 },
          color: RATIO_COLOR,
          data: ratio.map((row) => [row.date, row.detections_ratio]),
        },
      ],
    }),
    [ratio],
  )

  const dailyEmpty = emptyMessageOf(response, daily.length === 0)
  let ratioEmpty = emptyMessageOf(response, ratio.length === 0)
  if (ratioEmpty && daily.length > 0) {
    ratioEmpty =
      'No day has detections from both MODIS and VIIRS in this selection (the loaded data may contain only one sensor).'
  }

  return (
    <>
      <ChartCard
        number="23"
        title="MODIS vs VIIRS: daily detections"
        subtitle="Detections per UTC day, one line per sensor (never added together)."
        loading={loading}
        error={error}
        emptyMessage={dailyEmpty}
      >
        <EChart option={dailyOption} />
      </ChartCard>
      <ChartCard
        number="24"
        title="VIIRS / MODIS ratio"
        subtitle="VIIRS detections divided by MODIS detections, on days when both detected something."
        loading={loading}
        error={error}
        emptyMessage={ratioEmpty}
      >
        <EChart option={ratioOption} />
      </ChartCard>
    </>
  )
}

export default SensorComparisonCharts
