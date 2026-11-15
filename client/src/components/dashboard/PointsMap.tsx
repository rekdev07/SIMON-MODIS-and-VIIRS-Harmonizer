import { useMemo } from 'react'
import { useStats } from '../../hooks/useStats'
import { type PointRow, type StatsQuery } from '../../types/stats'
import {
  SENSOR_COLORS,
  emptyMessageOf,
  sensorsIn,
} from '../../utils/chartTheme'
import ChartCard from './ChartCard'
import MiniMap from './MiniMap'
import PointsLayer from './PointsLayer'

/** Props of {@link PointsMap}. */
type PointsMapProps = {
  query: StatsQuery
}

/** Points requested; the API returns the strongest FRP first when there are more. */
const POINTS_LIMIT = '5000'

/**
 * Chart 21: point map of detections from `/stats/points`, colored by sensor.
 * When the area holds more than the limit, the API keeps the most intense
 * detections and sets `metadata.truncated`, which the subtitle reports.
 */
function PointsMap({ query }: PointsMapProps) {
  const options = useMemo(() => ({ limit: POINTS_LIMIT }), [])
  const { response, loading, error } = useStats<PointRow[]>(
    'points',
    query,
    options,
  )
  const points = useMemo(() => response?.data ?? [], [response])
  const truncated = response?.metadata.truncated === true

  return (
    <ChartCard
      number="21"
      title="Detection map"
      subtitle={
        truncated
          ? `Showing the ${points.length.toLocaleString('en-US')} most intense detections (FRP); narrow the area or dates to see all.`
          : 'Every detection in the area, colored by sensor.'
      }
      loading={loading}
      error={error}
      emptyMessage={emptyMessageOf(response, points.length === 0)}
    >
      <MiniMap bounds={query.bounds}>
        <PointsLayer points={points} />
      </MiniMap>
      <ul className="mt-2 flex gap-4 text-xs text-gray-700">
        {sensorsIn(points).map((sensor) => (
          <li key={sensor} className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: SENSOR_COLORS[sensor] }}
            />
            {sensor}
          </li>
        ))}
      </ul>
    </ChartCard>
  )
}

export default PointsMap
