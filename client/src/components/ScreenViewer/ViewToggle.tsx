/** The main views of the app. */
export type MainView = 'map' | 'calendar' | 'dashboard'

/** Props of {@link ViewToggle}. */
type ViewToggleProps = {
  view: MainView
  onChange: (view: MainView) => void
}

/** Text-only labels: three icon + text buttons do not fit in the 300 px side panel. */
const OPTIONS: { view: MainView; label: string }[] = [
  { view: 'map', label: 'Map' },
  { view: 'calendar', label: 'Calendar' },
  { view: 'dashboard', label: 'Dashboard' },
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
      {OPTIONS.map(({ view: option, label }) => {
        const active = view === option
        return (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option)}
            className={`truncate rounded-md px-1 py-1.5 text-sm font-medium transition ${
              active
                ? 'bg-blue-600 text-white shadow'
                : 'text-gray-700 hover:bg-gray-300'
            }`}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}

export default ViewToggle
