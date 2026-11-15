/** The main views of the app. */
export type MainView = 'map' | 'calendar' | 'dashboard' | 'ml'

/** Props of {@link ViewToggle}. */
type ViewToggleProps = {
  view: MainView
  onChange: (view: MainView) => void
}

/** Text-only labels: three icon + text buttons do not fit in the 300 px side panel. */
const OPTIONS: { view: MainView; label: string; ariaLabel: string }[] = [
  { view: 'map', label: 'Map', ariaLabel: 'Map' },
  { view: 'calendar', label: 'Calendar', ariaLabel: 'Calendar' },
  { view: 'dashboard', label: 'Dashboard', ariaLabel: 'Dashboard' },
  { view: 'ml', label: 'ML', ariaLabel: 'Machine Learning' },
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
      className="mb-6 grid grid-cols-4 divide-x divide-gray-300 overflow-hidden rounded border border-gray-300 bg-white"
    >
      {OPTIONS.map(({ view: option, label, ariaLabel }) => {
        const active = view === option
        return (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={ariaLabel}
            title={ariaLabel}
            onClick={() => onChange(option)}
            className={`truncate px-1 py-2 text-sm font-medium transition ${
              active
                ? 'bg-blue-600 text-white'
                : 'text-gray-700 hover:bg-gray-100'
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
