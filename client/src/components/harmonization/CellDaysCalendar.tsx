import { useMemo } from 'react'
import { type CellDaysPeriod } from '../../types/stats'
import { AXIS_STYLE, LEGEND_STYLE } from '../../utils/chartTheme'
import { ZERO_COLOR, buildCountScale } from '../../utils/calendarScale'
import { MONTH_LABELS, periodTooltip } from '../../utils/cellDays'
import ChartCard from '../dashboard/ChartCard'
import EChart from '../dashboard/EChart'

/** Props of {@link CellDaysCalendar}. */
type CellDaysCalendarProps = {
  /** One row per calendar month from `/stats/celldays` (`data.months`). */
  months: CellDaysPeriod[]
  loading: boolean
  error: string | null
  emptyMessage: string | null
}

/** Marker of a month whose value is (partly) extrapolated from MODIS. */
const MARKER_STYLE = {
  color: '#ffffff',
  borderColor: '#1f2937',
  borderWidth: 1,
}

/** Chart height that leaves each year row readable, from a few years to 26. */
function heightFor(years: number): string {
  if (years <= 6) return 'h-72'
  if (years <= 14) return 'h-96'
  return 'h-[40rem]'
}

/**
 * Chart 28: fire calendar in cell-days, one row per year and one column per
 * month of the selection.
 *
 * Colors use the same binned YlOrRd scale as the burning activity calendar
 * (bins grow geometrically up to the largest month, so one extreme month
 * does not wash the rest out). A white diamond marks months extrapolated from
 * MODIS and a white circle months that mix VIIRS and MODIS days, so the
 * observed and the estimated parts of the record can be told apart at a
 * glance. Months without any satellite data stay blank.
 */
function CellDaysCalendar({
  months,
  loading,
  error,
  emptyMessage,
}: CellDaysCalendarProps) {
  const years = useMemo(
    () => [...new Set(months.map((m) => Number(m.start.slice(0, 4))))],
    [months],
  )

  const option = useMemo(() => {
    const withData = months.filter((m) => m.value !== null)
    const max = Math.max(1, ...withData.map((m) => m.value ?? 0))
    const steps = buildCountScale(max)
    const pieces = [
      { gte: 0, lt: 1, color: ZERO_COLOR, label: '0' },
      ...steps.map((step, i) => ({
        gte: i === 0 ? 1 : steps[i - 1].max,
        ...(step.max === Infinity ? {} : { lt: step.max }),
        color: step.color,
        label: step.label,
      })),
    ]
    // [column (month), row (year), value, index into `months`].
    const cell = (m: CellDaysPeriod) => [
      Number(m.start.slice(5, 7)) - 1,
      years.indexOf(Number(m.start.slice(0, 4))),
      m.value,
      months.indexOf(m),
    ]
    const marked = (source: CellDaysPeriod['source']) =>
      withData.filter((m) => m.source === source).map(cell)
    return {
      grid: { left: 48, right: 16, top: 28, bottom: 64 },
      legend: {
        ...LEGEND_STYLE,
        data: ['Extrapolated from MODIS', 'Mixed VIIRS + MODIS'],
      },
      tooltip: {
        formatter: (p: { data: number[] }) => {
          const m = months[p.data[3]]
          if (!m) return ''
          return periodTooltip(
            m,
            `${MONTH_LABELS[p.data[0]]} ${years[p.data[1]]}`,
          )
        },
      },
      xAxis: {
        type: 'category',
        data: MONTH_LABELS,
        ...AXIS_STYLE,
        splitArea: { show: false },
      },
      yAxis: {
        type: 'category',
        data: years.map(String),
        inverse: true,
        ...AXIS_STYLE,
      },
      visualMap: {
        type: 'piecewise',
        seriesIndex: 0,
        dimension: 2,
        pieces,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        itemWidth: 14,
        itemHeight: 10,
        textStyle: { fontSize: 11 },
      },
      series: [
        {
          type: 'heatmap',
          data: withData.map(cell),
          itemStyle: { borderColor: '#ffffff', borderWidth: 1 },
        },
        {
          name: 'Extrapolated from MODIS',
          type: 'scatter',
          symbol: 'diamond',
          symbolSize: 7,
          itemStyle: MARKER_STYLE,
          data: marked('extrapolated'),
        },
        {
          name: 'Mixed VIIRS + MODIS',
          type: 'scatter',
          symbol: 'circle',
          symbolSize: 6,
          itemStyle: MARKER_STYLE,
          data: marked('mixed'),
        },
      ],
    }
  }, [months, years])

  return (
    <ChartCard
      number="28"
      title="Fire calendar (cell-days)"
      subtitle="Cell-days per month and year. ◆ extrapolated from MODIS, ● mixed month, no marker = observed by VIIRS SNPP."
      loading={loading}
      error={error}
      emptyMessage={emptyMessage}
      wide
    >
      <EChart option={option} heightClass={heightFor(years.length)} />
    </ChartCard>
  )
}

export default CellDaysCalendar
