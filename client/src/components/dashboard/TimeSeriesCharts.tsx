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

/** Offset between kelvin (API unit of brightness) and degrees Celsius. */
const KELVIN_TO_CELSIUS = -273.15

/**
 * The series of charts 2, 4 and 5: field, title, unit and the offset added to
 * the API value before plotting (brightness arrives in kelvin and is shown in
 * °C, which reads more naturally).
 */
const SERIES: {
  number: string
  field: 'detections' | 'frp_mean' | 'bright_mir_mean'
  title: string
  unit: string
  offset: number
}[] = [
  {
    number: '2',
    field: 'detections',
    title: 'Detections over time',
    unit: 'detections',
    offset: 0,
  },
  {
    number: '4',
    field: 'frp_mean',
    title: 'Mean FRP over time',
    unit: 'MW',
    offset: 0,
  },
  {
    number: '5',
    field: 'bright_mir_mean',
    title: 'Mean MIR brightness over time',
    unit: '°C',
    offset: KELVIN_TO_CELSIUS,
  },
]

/** Line chart option: one line per sensor on a time axis. */
function lineOption(
  rows: TimeseriesRow[],
  { field, unit, offset }: (typeof SERIES)[number],
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
        .map((row) => {
          const value = row[field]
          return [row.period, value === null ? null : value + offset]
        }),
    })),
  }
}

/**
 * Charts 2, 4 and 5: detections, mean FRP and mean MIR brightness (°C) per
 * period and sensor, from one `/stats/timeseries` request.
 *
 * The frequency selector is repeated on every card but drives a single
 * state, so the three charts always show the same periods. Periods without
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
    () => SERIES.map((s) => lineOption(rows, s)),
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
