import { type StatsFilters } from '../../types/stats'
import MiniSelect from './MiniSelect'

/** Props of {@link DashboardFilters}. */
type DashboardFiltersProps = {
  filters: StatsFilters
  onChange: (filters: StatsFilters) => void
}

/** Options of each filter; `''` means "all" (the parameter is not sent). */
const FILTER_FIELDS: {
  key: keyof StatsFilters
  label: string
  options: { value: string; label: string }[]
}[] = [
  {
    key: 'instrument',
    label: 'Sensor',
    options: [
      { value: '', label: 'All sensors' },
      { value: 'MODIS', label: 'MODIS' },
      { value: 'VIIRS', label: 'VIIRS' },
    ],
  },
  {
    key: 'satellite',
    label: 'Satellite',
    options: [
      { value: '', label: 'All satellites' },
      { value: 'Terra', label: 'Terra (MODIS)' },
      { value: 'Aqua', label: 'Aqua (MODIS)' },
      { value: 'SNPP', label: 'SNPP (VIIRS)' },
      { value: 'NOAA-20', label: 'NOAA-20 (VIIRS)' },
      { value: 'NOAA-21', label: 'NOAA-21 (VIIRS)' },
    ],
  },
  {
    key: 'daynight',
    label: 'Day or night',
    options: [
      { value: '', label: 'Day and night' },
      { value: 'D', label: 'Day only' },
      { value: 'N', label: 'Night only' },
    ],
  },
  {
    key: 'confidence_min',
    label: 'Minimum confidence',
    options: [
      { value: 'low', label: 'Any confidence' },
      { value: 'nominal', label: 'Nominal or high' },
      { value: 'high', label: 'High only' },
    ],
  },
  {
    key: 'fire_type',
    label: 'Fire type',
    options: [
      { value: '0', label: 'Vegetation (+ unknown)' },
      { value: 'all', label: 'All types' },
      { value: '1', label: 'Volcano' },
      { value: '2', label: 'Static land source' },
      { value: '3', label: 'Offshore' },
    ],
  },
]

/**
 * One row of filters above the charts. Every chart re-fetches with the new
 * value; the API applies the same rules as `/api/v1/hotspots`. The default
 * fire type keeps vegetation fires and detections of unknown type, because
 * most near-real-time VIIRS data has no type.
 */
function DashboardFilters({ filters, onChange }: DashboardFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {FILTER_FIELDS.map((field) => (
        <MiniSelect
          key={field.key}
          label={field.label}
          value={filters[field.key]}
          options={field.options}
          onChange={(value) => onChange({ ...filters, [field.key]: value })}
        />
      ))}
    </div>
  )
}

export default DashboardFilters
