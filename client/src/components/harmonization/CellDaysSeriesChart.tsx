import { useMemo, useState } from 'react'
import { useStats } from '../../hooks/useStats'
import {
  type CellDaysData,
  type CellDaysFreq,
  type StatsQuery,
  type StatsResponse,
} from '../../types/stats'
import {
  AXIS_STYLE,
  GRID_LAYOUT,
  LEGEND_STYLE,
  emptyMessageOf,
} from '../../utils/chartTheme'
import {
  CELL_DAYS_COLORS,
  CELL_DAYS_LABELS,
  CELL_DAYS_UNIT,
  periodTooltip,
} from '../../utils/cellDays'
import ChartCard from '../dashboard/ChartCard'
import EChart from '../dashboard/EChart'
import MiniSelect from '../dashboard/MiniSelect'

/** Props of {@link CellDaysSeriesChart}. */
type CellDaysSeriesChartProps = {
  query: StatsQuery
  /**
   * The panel's monthly response, reused when "Monthly" is selected so the
   * same data is not requested twice.
   */
  monthly: StatsResponse<CellDaysData> | null
  monthlyLoading: boolean
  monthlyError: string | null
}

const FREQ_OPTIONS: { value: CellDaysFreq; label: string }[] = [
  { value: 'week', label: 'Weekly' },
  { value: 'month', label: 'Monthly' },
  { value: 'year', label: 'Yearly' },
]

/** Label of a period on the x axis: the year, the month or the first day. */
function periodLabel(start: string, freq: CellDaysFreq): string {
  if (freq === 'year') return start.slice(0, 4)
  if (freq === 'month') return start.slice(0, 7)
  return start
}

/**
 * Chart 26: cell-days per week, month or year from `/stats/celldays`.
 *
 * Each bar is stacked in two parts: the days observed by VIIRS SNPP (orange)
 * and the days extrapolated from MODIS (blue). Both are in the same unit, so
 * the bar height is the whole period and the colors show which part is an
 * estimate. A zoom slider appears when there are many bars (weeks over
 * several years).
 */
function CellDaysSeriesChart({
  query,
  monthly,
  monthlyLoading,
  monthlyError,
}: CellDaysSeriesChartProps) {
  const [freq, setFreq] = useState<CellDaysFreq>('month')
  const options = useMemo(() => ({ freq }), [freq])
  // Only fetch for weeks and years; months come from the panel.
  const own = useStats<CellDaysData>(
    'celldays',
    freq === 'month' ? null : query,
    options,
  )
  const response = freq === 'month' ? monthly : own.response
  const loading = freq === 'month' ? monthlyLoading : own.loading
  const error = freq === 'month' ? monthlyError : own.error
  const rows = useMemo(() => response?.data.series ?? [], [response])

  const option = useMemo(() => {
    const labels = rows.map((row) => periodLabel(row.start, freq))
    const zoom = rows.length > 60
    return {
      grid: { ...GRID_LAYOUT, bottom: zoom ? 72 : 40 },
      legend: LEGEND_STYLE,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: { dataIndex: number }[]) => {
          const row = rows[params[0]?.dataIndex ?? -1]
          if (!row) return ''
          const title =
            freq === 'week' || row.partial
              ? `${row.start} → ${row.end}`
              : labels[params[0].dataIndex]
          return periodTooltip(row, title)
        },
      },
      xAxis: { type: 'category', data: labels, ...AXIS_STYLE },
      yAxis: { type: 'value', name: CELL_DAYS_UNIT, ...AXIS_STYLE },
      dataZoom: zoom
        ? [{ type: 'inside' }, { type: 'slider', bottom: 8, height: 20 }]
        : [],
      series: (['viirs', 'extrapolated'] as const).map((part) => ({
        name: CELL_DAYS_LABELS[part],
        type: 'bar',
        stack: 'total',
        barCategoryGap: '20%',
        color: CELL_DAYS_COLORS[part],
        data: rows.map((row) => row[part]),
      })),
    }
  }, [rows, freq])

  return (
    <ChartCard
      number="26"
      title="Cell-days over time"
      subtitle="VIIRS SNPP-equivalent cell-days per period: observed (orange) and extrapolated from MODIS (blue). Indirect metric of fire activity."
      loading={loading}
      error={error}
      emptyMessage={emptyMessageOf(
        response,
        rows.length === 0 || !!response?.message,
      )}
      wide
      actions={
        <MiniSelect
          label="Period"
          value={freq}
          options={FREQ_OPTIONS}
          onChange={(value) => setFreq(value as CellDaysFreq)}
        />
      }
    >
      <EChart option={option} heightClass="h-80" />
    </ChartCard>
  )
}

export default CellDaysSeriesChart
