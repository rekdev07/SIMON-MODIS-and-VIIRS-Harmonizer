import { useMemo, useState } from 'react'
import { useStats } from '../../hooks/useStats'
import {
  type CalendarRow,
  type Sensor,
  type StatsQuery,
} from '../../types/stats'
import {
  AXIS_STYLE,
  SEQUENTIAL_RAMP,
  emptyMessageOf,
  formatNumber,
  sensorsIn,
} from '../../utils/chartTheme'
import ChartCard from './ChartCard'
import EChart from './EChart'
import MiniSelect from './MiniSelect'

/** Props of {@link CalendarChart}. */
type CalendarChartProps = {
  query: StatsQuery
}

type Metric = 'detections' | 'frp'
type Granularity = 'day' | 'week'

/**
 * Chart 11: burn calendar from `/stats/calendar`, a heat map with one row per
 * year and one column per day of year (or ISO week).
 *
 * Only one sensor is shown at a time (selector appears when both have data):
 * mixing them in one cell would add MODIS and VIIRS counts together. Color is
 * a single-hue sequential ramp, light = few, dark = many. Empty cells are days
 * without detections.
 */
function CalendarChart({ query }: CalendarChartProps) {
  const [metric, setMetric] = useState<Metric>('detections')
  const [granularity, setGranularity] = useState<Granularity>('day')
  const [chosenSensor, setChosenSensor] = useState<Sensor | null>(null)
  const options = useMemo(
    () => ({ metric, granularity }),
    [metric, granularity],
  )
  const { response, loading, error } = useStats<CalendarRow[]>(
    'calendar',
    query,
    options,
  )
  const rows = useMemo(() => response?.data ?? [], [response])
  const sensors = useMemo(() => sensorsIn(rows), [rows])
  const sensor =
    chosenSensor && sensors.includes(chosenSensor) ? chosenSensor : sensors[0]
  const unit = metric === 'frp' ? 'MW' : 'detections'

  const option = useMemo(() => {
    const own = rows.filter((row) => row.sensor === sensor)
    const years = [...new Set(own.map((row) => row.year))].sort()
    const columns = granularity === 'day' ? 366 : 53
    const values = own.map((row) => row.value ?? 0)
    return {
      grid: { left: 48, right: 16, top: 8, bottom: 104 },
      tooltip: {
        formatter: (p: { value: [number, number, number, string] }) =>
          `${p.value[3]}<br/>${formatNumber(p.value[2])} ${unit}`,
      },
      xAxis: {
        type: 'category',
        name: granularity === 'day' ? 'Day of year' : 'ISO week',
        nameLocation: 'middle',
        nameGap: 24,
        data: Array.from({ length: columns }, (_, i) => String(i + 1)),
        ...AXIS_STYLE,
        splitArea: { show: false },
      },
      yAxis: {
        type: 'category',
        data: years.map(String),
        ...AXIS_STYLE,
      },
      visualMap: {
        // Color by the value (3rd element); by default ECharts uses the last
        // element of each point, which here is the date string.
        dimension: 2,
        min: 0,
        max: Math.max(1, ...values),
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        itemHeight: 120,
        textStyle: { fontSize: 11 },
        inRange: { color: SEQUENTIAL_RAMP },
      },
      series: [
        {
          type: 'heatmap',
          // [column index, row index, value, date]; the category index is
          // 0-based while the day/week number from the API is 1-based.
          data: own.map((row) => [
            ((granularity === 'day' ? row.day_of_year : row.week) ?? 1) - 1,
            years.indexOf(row.year),
            row.value ?? 0,
            row.date,
          ]),
        },
      ],
    }
  }, [rows, sensor, granularity, unit])

  return (
    <ChartCard
      number="11"
      title="Burn calendar"
      subtitle={`${sensor ?? 'Per sensor'}: ${metric === 'frp' ? 'total FRP (MW)' : 'detections'} per ${granularity === 'day' ? 'day' : 'week'} and year (UTC).`}
      loading={loading}
      error={error}
      emptyMessage={emptyMessageOf(response, rows.length === 0)}
      wide
      actions={
        <>
          <MiniSelect
            label="Metric"
            value={metric}
            options={[
              { value: 'detections', label: 'Detections' },
              { value: 'frp', label: 'Total FRP' },
            ]}
            onChange={(value) => setMetric(value as Metric)}
          />
          <MiniSelect
            label="Granularity"
            value={granularity}
            options={[
              { value: 'day', label: 'By day' },
              { value: 'week', label: 'By week' },
            ]}
            onChange={(value) => setGranularity(value as Granularity)}
          />
          {sensors.length > 1 && sensor && (
            <MiniSelect
              label="Sensor"
              value={sensor}
              options={sensors.map((s) => ({ value: s, label: s }))}
              onChange={(value) => setChosenSensor(value as Sensor)}
            />
          )}
        </>
      }
    >
      <EChart option={option} heightClass="h-72" />
    </ChartCard>
  )
}

export default CalendarChart
