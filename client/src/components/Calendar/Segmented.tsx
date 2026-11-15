/** Props of {@link Segmented}. */
type SegmentedProps<T extends string> = {
  /** Accessible name of the group, e.g. "Sensor". */
  label: string
  options: readonly (readonly [T, string])[]
  value: T
  onChange: (value: T) => void
}

/**
 * Small segmented control (a radio group drawn as joined buttons) used by the
 * calendar for its sensor and color-mode switches.
 */
function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: SegmentedProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="flex divide-x divide-gray-300 overflow-hidden rounded border border-gray-300 bg-white text-xs"
    >
      {options.map(([option, text]) => (
        <button
          key={option}
          type="button"
          role="radio"
          aria-checked={value === option}
          onClick={() => onChange(option)}
          className={`px-3 py-1 transition ${
            value === option
              ? 'bg-blue-600 font-semibold text-white'
              : 'text-gray-700 hover:bg-gray-100'
          }`}
        >
          {text}
        </button>
      ))}
    </div>
  )
}

export default Segmented
