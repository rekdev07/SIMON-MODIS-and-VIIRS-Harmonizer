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

/** Column labels of the calendar, one per month. */
const MONTH_LABELS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]

/**
 * Chart 11: burn calendar from `/stats/calendar`, a heat map with one row per
 * year and one column per month.
 *
 * The API answers per day, so the daily values are summed per year and month
 * here. Both metrics are totals (detections, total FRP), so the sum is exact.
 *
 * Only one sensor is shown at a time (selector appears when both have data):
 * mixing them in one cell would add MODIS and VIIRS counts together. Color is
 * a single-hue sequential ramp, light = few, dark = many. Empty cells are
 * months without detections.
 */
function CalendarChart({ query }: CalendarChartProps) {
  const [metric, setMetric] = useState<Metric>('detections')
  const [chosenSensor, setChosenSensor] = useState<Sensor | null>(null)
  const options = useMemo(() => ({ metric, granularity: 'day' }), [metric])
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
    // Sum of the daily values per "year-month" (month 0-based).
    const totals = new Map<string, number>()
    for (const row of rows) {
      if (row.sensor !== sensor) continue
      const month = Number(row.date.slice(5, 7)) - 1
      const key = `${row.year}-${month}`
      totals.set(key, (totals.get(key) ?? 0) + (row.value ?? 0))
    }
    const cells = [...totals].map(([key, value]) => {
      const [year, month] = key.split('-').map(Number)
      return { year, month, value }
    })
    const years = [...new Set(cells.map((cell) => cell.year))].sort()
    const values = cells.map((cell) => cell.value)
    return {
      grid: { left: 48, right: 16, top: 8, bottom: 104 },
      tooltip: {
        formatter: (p: { value: [number, number, number, string] }) =>
          `${p.value[3]}<br/>${formatNumber(p.value[2])} ${unit}`,
      },
      xAxis: {
        type: 'category',
        name: 'Month',
        nameLocation: 'middle',
        nameGap: 24,
        data: MONTH_LABELS,
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
          // [column index, row index, value, label].
          data: cells.map((cell) => [
            cell.month,
            years.indexOf(cell.year),
            cell.value,
            `${MONTH_LABELS[cell.month]} ${cell.year}`,
          ]),
        },
      ],
    }
  }, [rows, sensor, unit])

  return (
    <ChartCard
      number="11"
      title="Burn calendar"
      subtitle={`${sensor ?? 'Per sensor'}: ${metric === 'frp' ? 'total FRP (MW)' : 'detections'} per month and year (UTC).`}
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
