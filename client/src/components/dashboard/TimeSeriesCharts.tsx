import { useMemo, useState } from 'react'
import { useStats } from '../../hooks/useStats'
import { type StatsQuery, type TimeseriesRow } from '../../types/stats'
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
import EChart, { type EChartOption } from './EChart'
import MiniSelect from './MiniSelect'

/** Props of {@link TimeSeriesCharts}. */
type TimeSeriesChartsProps = {
  query: StatsQuery
}

type Freq = 'day' | 'week' | 'month'

const FREQ_OPTIONS = [
  { value: 'day', label: 'Daily' },
  { value: 'week', label: 'Weekly' },
  { value: 'month', label: 'Monthly' },
]

/** The four series of charts 2-5: field, title and unit. */
const SERIES: {
  number: string
  field: 'detections' | 'frp_total' | 'frp_mean' | 'bright_mir_mean'
  title: string
  unit: string
}[] = [
  {
    number: '2',
    field: 'detections',
    title: 'Detections over time',
    unit: 'detections',
  },
  { number: '3', field: 'frp_total', title: 'Total FRP over time', unit: 'MW' },
  { number: '4', field: 'frp_mean', title: 'Mean FRP over time', unit: 'MW' },
  {
    number: '5',
    field: 'bright_mir_mean',
    title: 'Mean MIR brightness over time',
    unit: 'K',
  },
]

/** Line chart option: one line per sensor on a time axis. */
function lineOption(
  rows: TimeseriesRow[],
  field: (typeof SERIES)[number]['field'],
  unit: string,
): EChartOption {
  return {
    grid: GRID_LAYOUT,
    legend: LEGEND_STYLE,
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value: number | null) =>
        `${formatNumber(value)} ${unit}`,
    },
    xAxis: { type: 'time', ...AXIS_STYLE, splitLine: { show: false } },
    yAxis: { type: 'value', name: unit, ...AXIS_STYLE },
    series: sensorsIn(rows).map((sensor) => ({
      name: sensor,
      type: 'line',
      showSymbol: false,
      lineStyle: { width: 2 },
      color: SENSOR_COLORS[sensor],
      data: rows
        .filter((row) => row.sensor === sensor)
        .map((row) => [row.period, row[field]]),
    })),
  }
}

/**
 * Charts 2-5: detections, total FRP, mean FRP and mean MIR brightness per
 * period and sensor, from one `/stats/timeseries` request.
 *
 * The frequency selector is repeated on every card but drives a single
 * state, so the four charts always show the same periods. Periods without
 * detections are absent from the API answer, so lines simply connect the
 * periods that exist.
 */
function TimeSeriesCharts({ query }: TimeSeriesChartsProps) {
  const [freq, setFreq] = useState<Freq>('week')
  const options = useMemo(() => ({ freq }), [freq])
  const { response, loading, error } = useStats<TimeseriesRow[]>(
    'timeseries',
    query,
    options,
  )
  const rows = useMemo(() => response?.data ?? [], [response])
  const chartOptions = useMemo(
    () => SERIES.map((s) => lineOption(rows, s.field, s.unit)),
    [rows],
  )
  const emptyMessage = emptyMessageOf(response, rows.length === 0)

  return (
    <>
      {SERIES.map((s, index) => (
        <ChartCard
          key={s.field}
          number={s.number}
          title={s.title}
          subtitle={`Per sensor, ${s.unit}. Period start date (UTC); weeks start on Monday.`}
          loading={loading}
          error={error}
          emptyMessage={emptyMessage}
          actions={
            <MiniSelect
              label="Period length"
              value={freq}
              options={FREQ_OPTIONS}
              onChange={(value) => setFreq(value as Freq)}
            />
          }
        >
          <EChart option={chartOptions[index]} />
        </ChartCard>
      ))}
    </>
  )
}

export default TimeSeriesCharts
