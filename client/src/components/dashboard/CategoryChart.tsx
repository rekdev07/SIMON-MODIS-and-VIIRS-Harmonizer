import { useMemo } from 'react'
import { useStats } from '../../hooks/useStats'
import { type CategoryRow, type StatsQuery } from '../../types/stats'
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

type CategoryField = 'daynight' | 'satellite' | 'type' | 'confidence_level'

/** Readable names of the raw category codes, per field. */
const CATEGORY_LABELS: Record<CategoryField, Record<string, string>> = {
  daynight: { D: 'Day', N: 'Night' },
  satellite: {},
  type: {
    '0': 'Vegetation',
    '1': 'Volcano',
    '2': 'Static land source',
    '3': 'Offshore',
  },
  confidence_level: { low: 'Low', nominal: 'Nominal', high: 'High' },
}

/** Display order of known categories (others follow in API order). */
const CATEGORY_ORDER: Record<CategoryField, string[]> = {
  daynight: ['D', 'N'],
  satellite: ['Terra', 'Aqua', 'SNPP', 'NOAA-20', 'NOAA-21'],
  type: ['0', '1', '2', '3'],
  confidence_level: ['low', 'nominal', 'high'],
}

/** Props of {@link CategoryChart}. */
type CategoryChartProps = {
  query: StatsQuery
  number: string
  title: string
  field: CategoryField
}

/**
 * Charts 13-16: detections per category and sensor (bars), with the mean FRP
 * in the tooltip, from `/stats/by-category`.
 *
 * For `field="type"` the request overrides the type filter with
 * `fire_type=all`; otherwise the default filter would leave only type 0.
 * A `null` category means the type (or other field) is unknown.
 */
function CategoryChart({ query, number, title, field }: CategoryChartProps) {
  const options = useMemo(
    (): Record<string, string> =>
      field === 'type' ? { field, fire_type: 'all' } : { field },
    [field],
  )
  const { response, loading, error } = useStats<CategoryRow[]>(
    'by-category',
    query,
    options,
  )
  const rows = useMemo(() => response?.data ?? [], [response])

  const option = useMemo(() => {
    const keyOf = (row: CategoryRow) => String(row.category ?? 'unknown')
    const present = [...new Set(rows.map(keyOf))]
    const order = CATEGORY_ORDER[field]
    const categories = [
      ...order.filter((key) => present.includes(key)),
      ...present.filter((key) => !order.includes(key)),
    ]
    const label = (key: string) =>
      key === 'unknown' ? 'Unknown' : (CATEGORY_LABELS[field][key] ?? key)
    return {
      grid: GRID_LAYOUT,
      legend: LEGEND_STYLE,
      tooltip: {
        trigger: 'item',
        formatter: (p: {
          seriesName: string
          name: string
          value: number
          data: { frp: number | null }
        }) =>
          `${p.seriesName} · ${p.name}<br/>${formatNumber(p.value, 0)} detections` +
          `<br/>Mean FRP: ${formatNumber(p.data.frp)} MW`,
      },
      xAxis: {
        type: 'category',
        data: categories.map(label),
        ...AXIS_STYLE,
      },
      yAxis: { type: 'value', name: 'detections', ...AXIS_STYLE },
      series: sensorsIn(rows).map((sensor) => ({
        name: sensor,
        type: 'bar',
        itemStyle: { borderRadius: [4, 4, 0, 0] },
        color: SENSOR_COLORS[sensor],
        data: categories.map((key) => {
          const row = rows.find((r) => r.sensor === sensor && keyOf(r) === key)
          return { value: row?.detections ?? 0, frp: row?.frp_mean ?? null }
        }),
      })),
    }
  }, [rows, field])

  return (
    <ChartCard
      number={number}
      title={title}
      subtitle={`Detections per category and sensor; mean FRP (MW) on hover.${field === 'type' ? ' Shows every type, whatever the type filter.' : ''}`}
      loading={loading}
      error={error}
      emptyMessage={emptyMessageOf(response, rows.length === 0)}
    >
      <EChart option={option} heightClass="h-64" />
    </ChartCard>
  )
}

export default CategoryChart
