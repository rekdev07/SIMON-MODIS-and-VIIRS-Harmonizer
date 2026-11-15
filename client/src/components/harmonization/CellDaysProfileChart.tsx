import { useMemo } from 'react'
import { type CellDaysProfileRow } from '../../types/stats'
import { AXIS_STYLE, GRID_LAYOUT, formatNumber } from '../../utils/chartTheme'
import { CELL_DAYS_UNIT, MONTH_LABELS } from '../../utils/cellDays'
import ChartCard from '../dashboard/ChartCard'
import EChart from '../dashboard/EChart'

/** Props of {@link CellDaysProfileChart}. */
type CellDaysProfileChartProps = {
  /** Twelve rows from `/stats/celldays` (`data.profile`). */
  rows: CellDaysProfileRow[]
  loading: boolean
  error: string | null
  emptyMessage: string | null
}

/** Bar color of the average (neutral: a month mixes observed and extrapolated years). */
const MEAN_COLOR = '#d94801'

/**
 * Chart 27: average cell-days of each calendar month over the selected years.
 *
 * The bar is the mean; the tooltip adds the lowest and highest year and how
 * many years took part. Min and max are not drawn because one extreme year
 * (e.g. 2011 in Durango) would set the scale and flatten every bar. Only full
 * months take part (computed by the API), so a selection that starts
 * mid-month does not pull its month down.
 */
function CellDaysProfileChart({
  rows,
  loading,
  error,
  emptyMessage,
}: CellDaysProfileChartProps) {
  const option = useMemo(
    () => ({
      grid: GRID_LAYOUT,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: { dataIndex: number }[]) => {
          const row = rows[params[0]?.dataIndex ?? -1]
          if (!row) return ''
          if (row.years === 0) {
            return `<b>${MONTH_LABELS[row.month - 1]}</b><br/>No full month with data`
          }
          return (
            `<b>${MONTH_LABELS[row.month - 1]}</b><br/>` +
            `Mean ${formatNumber(row.mean)} ${CELL_DAYS_UNIT}<br/>` +
            `Range ${formatNumber(row.min)} – ${formatNumber(row.max)}<br/>` +
            `${row.years} year(s)`
          )
        },
      },
      xAxis: { type: 'category', data: MONTH_LABELS, ...AXIS_STYLE },
      yAxis: { type: 'value', name: CELL_DAYS_UNIT, ...AXIS_STYLE },
      series: [
        {
          name: 'Mean per year',
          type: 'bar',
          color: MEAN_COLOR,
          data: rows.map((row) => row.mean),
        },
      ],
    }),
    [rows],
  )

  return (
    <ChartCard
      number="27"
      title="Average by month"
      subtitle="Mean cell-days of each calendar month over the selected years (full months only). Hover a bar for the lowest and highest year."
      loading={loading}
      error={error}
      emptyMessage={emptyMessage}
      wide
    >
      <EChart option={option} />
    </ChartCard>
  )
}

export default CellDaysProfileChart
