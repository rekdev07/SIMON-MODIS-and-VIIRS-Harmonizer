import { useMemo } from 'react'
import { useStats } from '../../hooks/useStats'
import { type MonthlyRow, type StatsQuery } from '../../types/stats'
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

/** Props of {@link MonthlyChart}. */
type MonthlyChartProps = {
  query: StatsQuery
}

const MONTHS = [
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
 * Chart 25: seasonality from `/stats/monthly`, detections per calendar month
 * with every selected year added together (per sensor). The tooltip tells how
 * many years contributed, so a multi-year selection can be read as a yearly
 * average. For a month-by-month timeline see charts 2-5 with "Monthly".
 */
function MonthlyChart({ query }: MonthlyChartProps) {
  const { response, loading, error } = useStats<MonthlyRow[]>('monthly', query)
  const rows = useMemo(() => response?.data ?? [], [response])

  const option = useMemo(
    () => ({
      grid: GRID_LAYOUT,
      legend: LEGEND_STYLE,
      tooltip: {
        trigger: 'item',
        formatter: (p: {
          seriesName: string
          name: string
          value: number
          data: { years: number }
        }) =>
          `${p.seriesName} · ${p.name}<br/>${formatNumber(p.value, 0)} detections` +
          `<br/>${p.data.years} year(s) with data`,
      },
      xAxis: { type: 'category', data: MONTHS, ...AXIS_STYLE },
      yAxis: { type: 'value', name: 'detections', ...AXIS_STYLE },
      series: sensorsIn(rows).map((sensor) => ({
        name: sensor,
        type: 'bar',
        itemStyle: { borderRadius: 0 },
        color: SENSOR_COLORS[sensor],
        data: MONTHS.map((_, index) => {
          const row = rows.find(
            (r) => r.sensor === sensor && r.month === index + 1,
          )
          return {
            value: row?.detections ?? 0,
            years: row?.years_with_data ?? 0,
          }
        }),
      })),
    }),
    [rows],
  )

  return (
    <ChartCard
      number="25"
      title="Seasonality by month"
      subtitle="Detections per calendar month, all selected years together."
      loading={loading}
      error={error}
      emptyMessage={emptyMessageOf(response, rows.length === 0)}
    >
      <EChart option={option} />
    </ChartCard>
  )
}

export default MonthlyChart
