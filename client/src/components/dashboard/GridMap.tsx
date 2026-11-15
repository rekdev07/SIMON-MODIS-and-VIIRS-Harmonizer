import { useCallback, useMemo, useState } from 'react'
import { useStats } from '../../hooks/useStats'
import { type GridRow, type Sensor, type StatsQuery } from '../../types/stats'
import {
  SEQUENTIAL_RAMP,
  emptyMessageOf,
  formatNumber,
  sensorsIn,
} from '../../utils/chartTheme'
import ChartCard from './ChartCard'
import GridLayer from './GridLayer'
import MiniMap from './MiniMap'
import MiniSelect from './MiniSelect'

/** Props of {@link GridMap}. */
type GridMapProps = {
  query: StatsQuery
}

const CELL_OPTIONS = [
  { value: '0.1', label: '0.1° cells' },
  { value: '0.25', label: '0.25° cells' },
  { value: '0.5', label: '0.5° cells' },
  { value: '1', label: '1° cells' },
]

/** Number of color classes (one per step of the sequential ramp). */
const CLASSES = SEQUENTIAL_RAMP.length

/**
 * Chart 22: heat map of detections per grid cell from `/stats/grid`.
 *
 * One sensor at a time (a selector appears when both have data), because a
 * cell holding MODIS + VIIRS counts would mix incomparable units. Counts are
 * very skewed (a few cells hold most detections), so the color class uses a
 * log scale: `class = floor(log(1 + n) / log(1 + max) * classes)`, and the
 * legend shows the detection count where each class starts.
 */
function GridMap({ query }: GridMapProps) {
  const [cell, setCell] = useState('0.25')
  const [chosenSensor, setChosenSensor] = useState<Sensor | null>(null)
  const options = useMemo(() => ({ cell }), [cell])
  const { response, loading, error } = useStats<GridRow[]>(
    'grid',
    query,
    options,
  )
  const rows = useMemo(() => response?.data ?? [], [response])
  const sensors = useMemo(() => sensorsIn(rows), [rows])
  const sensor =
    chosenSensor && sensors.includes(chosenSensor) ? chosenSensor : sensors[0]
  const cells = useMemo(
    () => rows.filter((row) => row.sensor === sensor),
    [rows, sensor],
  )
  const logMax = Math.log1p(Math.max(1, ...cells.map((row) => row.detections)))

  const colorOf = useCallback(
    (detections: number) => {
      const index = Math.floor((Math.log1p(detections) / logMax) * CLASSES)
      return SEQUENTIAL_RAMP[Math.min(CLASSES - 1, index)]
    },
    [logMax],
  )
  const classStarts = SEQUENTIAL_RAMP.map((_, i) =>
    Math.ceil(Math.expm1((logMax * i) / CLASSES)),
  )

  return (
    <ChartCard
      number="22"
      title="Detection density"
      subtitle={`${sensor ?? 'Per sensor'}: detections per grid cell; total FRP (MW) on hover.`}
      loading={loading}
      error={error}
      emptyMessage={emptyMessageOf(response, rows.length === 0)}
      actions={
        <>
          <MiniSelect
            label="Cell size"
            value={cell}
            options={CELL_OPTIONS}
            onChange={setCell}
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
      <MiniMap bounds={query.bounds}>
        <GridLayer cells={cells} cell={Number(cell)} colorOf={colorOf} />
      </MiniMap>
      <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-700">
        {SEQUENTIAL_RAMP.map((color, i) => (
          <li key={color} className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-4 rounded-sm border border-gray-300"
              style={{ backgroundColor: color }}
            />
            ≥ {formatNumber(Math.max(1, classStarts[i]), 0)}
          </li>
        ))}
      </ul>
    </ChartCard>
  )
}

export default GridMap
