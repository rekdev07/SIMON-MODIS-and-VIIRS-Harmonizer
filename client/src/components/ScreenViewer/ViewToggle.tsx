import { CalendarDays, ChartColumn, MapIcon } from 'lucide-react'

/** The main views of the app. */
export type MainView = 'map' | 'calendar' | 'dashboard'

/** Props of {@link ViewToggle}. */
type ViewToggleProps = {
  view: MainView
  onChange: (view: MainView) => void
}

const OPTIONS: { view: MainView; label: string; Icon: typeof MapIcon }[] = [
  { view: 'map', label: 'Map', Icon: MapIcon },
  { view: 'calendar', label: 'Calendar', Icon: CalendarDays },
  { view: 'dashboard', label: 'Dashboard', Icon: ChartColumn },
]

/**
 * Segmented toggle under the SIMON title that swaps the main area between the
 * map, the burning activity calendar and the dashboard. All views share the
 * area, dates and filters chosen in the side panel, so switching never loses
 * the selection.
 */
function ViewToggle({ view, onChange }: ViewToggleProps) {
  return (
    <div
      role="radiogroup"
      aria-label="Main view"
      className="mb-6 grid grid-cols-3 rounded-lg bg-gray-200 p-1"
    >
      {OPTIONS.map(({ view: option, label, Icon }) => {
        const active = view === option
        return (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option)}
            className={`flex items-center justify-center gap-1.5 rounded-md py-1.5 text-sm font-medium transition ${
              active
                ? 'bg-blue-600 text-white shadow'
                : 'text-gray-700 hover:bg-gray-300'
            }`}
          >
            <Icon size={16} aria-hidden />
            {label}
          </button>
        )
      })}
    </div>
  )
}

export default ViewToggle
